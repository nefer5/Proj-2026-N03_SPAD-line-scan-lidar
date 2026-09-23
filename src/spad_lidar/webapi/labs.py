from pathlib import Path
from hashlib import sha256
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from typing import Literal
from ..models import SimulationConfig
from ..configuration import read_yaml, Algorithms, parse_yaml
from ..runtime.jobs import manager
from ..processing.records import histogram_records

router = APIRouter()
WEB = Path(__file__).resolve().parents[3]/'web'


def lab_page(kind):
    html = (WEB/'labs.html').read_text(encoding='utf-8').replace('__KIND__', kind)
    for name in ('styles.css', 'shared/labs.css', 'shared/labs.js', 'shared/spatial.js', 'curve-editor.js',
                 'vendor/katex/katex.min.js', 'vendor/katex/katex.min.css'):
        digest = sha256((WEB/name).read_bytes()).hexdigest()
        html = html.replace(f'/static/{name}"', f'/static/{name}?v={digest}"')
    return HTMLResponse(html)


@router.get('/spad')
def spad_page():
    return lab_page('spad')


@router.get('/system')
def system_page():
    return lab_page('system')


@router.post('/api/experiments/system/optical-data')
def export_optical_data(config: dict):
    try:
        from ..experiments.spatial import optical_dataset
        a=Algorithms.load()
        cfg=SimulationConfig.for_experiment('system',config,a)
        return optical_dataset(cfg,a).model_dump()
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/optics/validate')
def validate_optical_data(document: str = Body(media_type='text/plain')):
    try:
        from ..adapters.optical_data import validate_dataset
        return validate_dataset(parse_yaml(document),Algorithms.load()).model_dump()
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.get('/api/experiments/{kind}')
def experiment_catalog(kind: str):
    try:
        cfg = SimulationConfig.for_experiment(kind, {})
        curves = read_yaml('curve-inputs.yaml')
        curves['groups'] = {k: v for k, v in curves['groups'].items() if k in type(cfg.spectral_inputs).model_fields}
        curves.update(formulas=read_yaml('formulas.yaml'), formula_notes=read_yaml('formula-notes.yaml'))
        return {'defaults': cfg.model_dump(), 'schema': type(cfg).model_json_schema(),
                'help': read_yaml('parameter-help.yaml'), 'curves': curves,
                'algorithms': Algorithms.load().model_dump(), 'readout_modes': read_yaml('readout-modes.yaml')}
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/experiments/{kind}/validate')
def validate_experiment(kind: str, config: dict):
    try:
        return SimulationConfig.for_experiment(kind, config).model_dump()
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


class JobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['a', 'spad', 'system']
    config: dict


@router.post('/api/jobs')
def create_job(request: JobRequest):
    try:
        return manager().submit(request.kind, request.config)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/api/jobs')
def jobs():
    return manager().list()


@router.get('/api/jobs/{job_id}')
def job(job_id: str):
    try:
        return manager().get(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    try:
        return manager().cancel(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/api/jobs/{job_id}/result')
def result(job_id: str):
    try:
        return manager().result(job_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, str(exc)) from exc


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    bin_ps: float


@router.post('/api/jobs/{job_id}/replay')
def replay(job_id: str, request: ReplayRequest):
    try:
        result = manager().result(job_id)
        records = result['records']
        original = result['record_schema']['tdc_bin_ps']
        if request.bin_ps < original or not np.isclose(request.bin_ps/original, round(request.bin_ps/original), rtol=0, atol=np.finfo(float).eps*max(1,request.bin_ps/original)):
            raise ValueError('Replay bin must be an integer multiple of acquisition resolution')
        cfg = result['configuration']['experiment']
        h = result['histogram']
        return histogram_records(records, cfg['timing']['gate_start_ns'], cfg['timing']['gate_width_ns'], request.bin_ps, len(h['counts']))
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/experiments/{kind}/import')
def import_experiment(kind: str, document: str = Body(media_type='text/plain')):
    try:
        envelope = parse_yaml(document)
        if set(envelope) != {'schema_version', 'kind', 'experiment'} or envelope['schema_version'] != 2 or envelope['kind'] != kind:
            raise ValueError('Expected schema_version 2 and matching experiment kind; legacy A uses its own import entry')
        return SimulationConfig.for_experiment(kind, envelope['experiment']).model_dump()
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc

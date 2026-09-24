from pathlib import Path
from hashlib import sha256
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse,Response
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
    for name in ('styles.css', 'shared/labs.css', 'shared/labs.js', 'shared/spatial.js', 'shared/scan.js', 'curve-editor.js',
                 'vendor/katex/katex.min.js', 'vendor/katex/katex.min.css'):
        digest = sha256((WEB/name).read_bytes()).hexdigest()
        html = html.replace(f'/static/{name}"', f'/static/{name}?v={digest}"')
    return HTMLResponse(html)


@router.get('/spad')
def spad_page():
    return lab_page('spad')


@router.get('/system')
def system_page():
    return workspace_page('system')


def workspace_page(kind):
    html=(WEB/'system.html').read_text(encoding='utf-8')
    html=html.replace('data-lab="system"',f'data-lab="{kind}"')
    for name in ('system.css','system.js','shared/scan-workspace.js','shared/optical-panels.js','shared/histogram-window.js','curve-editor.js',
                 'vendor/katex/katex.min.js','vendor/katex/katex.min.css'):
        html=html.replace(f'/static/{name}"',f'/static/{name}?v={sha256((WEB/name).read_bytes()).hexdigest()}"')
    return HTMLResponse(html)


@router.get('/system/scan')
def scan_page():
    return workspace_page('scan')


@router.post('/api/experiments/{kind}/optical-data')
def export_optical_data(kind: str, config: dict):
    try:
        if kind not in ('system','scan'):
            raise ValueError('Optical data export requires a system experiment')
        from ..experiments.spatial import optical_dataset
        a=Algorithms.load()
        cfg=SimulationConfig.for_experiment(kind,config,a)
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
        result={'defaults': cfg.model_dump(), 'schema': type(cfg).model_json_schema(),
                'help': read_yaml('parameter-help.yaml'), 'curves': curves,
                'algorithms': Algorithms.load().model_dump(), 'readout_modes': read_yaml('readout-modes.yaml')}
        if kind in ('system','scan'):
            from ..experiments.system_config import form_values,LEGACY_PATHS
            form=form_values(cfg)
            paths={old:new for old,new in LEGACY_PATHS.items() if old=='rng_seed' or old.split('.')[1] in form.get(old.split('.')[0],{})}
            for group in ('scan','scene_motion'):
                if group in form:paths.update({group+'.'+k:group+'.'+k for k in form[group]})
            result.update(form_defaults=form,form_paths=paths,schema_version=3)
        return result
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
    kind: Literal['a', 'spad', 'system', 'scan']
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


@router.get('/api/jobs/{job_id}/system-view')
def system_result_view(job_id:str):
    """Decorate old immutable records for display without recalculating acquisition."""
    try:
        result=manager().result(job_id)
        if 'optics' not in result or 'scan' in result:
            raise ValueError('Expected a static B result')
        if 'form_configuration' not in result:
            from ..reporting.spatial_view import optical_view
            # Historical algorithms may predate display-only keys. Keep original
            # acquisition provenance and explicitly identify current view metadata.
            a=Algorithms.from_snapshot(result['configuration']['algorithms'])
            cfg=SimulationConfig.for_experiment('system',result['configuration']['experiment'],a)
            result.update(optical_view(cfg,a,result['optics']))
            result['view_note']='历史采集记录原样保留；仅补充显示元数据，未重新采样。旧版未保存的重复统计不补造。'
        return result
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    bin_ps: float


@router.post('/api/jobs/{job_id}/replay')
def replay(job_id: str, request: ReplayRequest):
    try:
        result = manager().result(job_id)
        if 'statistics' in result and 'references' in result:
            from ..experiments.spatial_analysis import replay_analysis
            a=Algorithms.model_validate(result['configuration']['algorithms'])
            cfg=SimulationConfig.for_experiment('system',result['configuration']['experiment'],a)
            return replay_analysis(result,cfg,a,request.bin_ps)
        records = result['records']
        original = result['record_schema']['tdc_bin_ps']
        if request.bin_ps < original or not np.isclose(request.bin_ps/original, round(request.bin_ps/original), rtol=0, atol=np.finfo(float).eps*max(1,request.bin_ps/original)):
            raise ValueError('Replay bin must be an integer multiple of acquisition resolution')
        cfg = result['configuration']['experiment']
        h = result['histogram']
        return histogram_records(records, cfg['timing']['gate_start_ns'], cfg['timing']['gate_width_ns'], request.bin_ps, len(h['counts']))
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/experiments/scan/preview')
def preview_scan(config: dict):
    try:
        from ..scan.schedule import build_schedule
        from ..scan.aggregation import count_pulses
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('scan',config,a)
        program,schedule,edges,budget=build_schedule(cfg,a)
        counts=count_pulses(schedule,cfg.scan.frame_count,budget['frame_period_ns'],len(edges)-1)
        rows=[r for r in schedule if r['measured']]
        return {'schedule':rows,'angle_edges_mrad':edges.tolist(),'angle_bin_centers_mrad':((edges[:-1]+edges[1:])/2).tolist(),
                'frame_budget':budget,'assigned_pulses_per_frame_bin':counts['assigned'].tolist(),
                'true_useful_pulses_per_frame_bin':counts['true_useful'].tolist(),
                'actual_emissions_per_frame_bin':counts['actual'].tolist(),
                'summary':{'scheduled_slots':len(rows),'emitted_reference_slots':sum(r['emitted'] for r in rows),
                           'blanked_slots':sum(not r['emitted'] for r in rows),'assigned_pulses':int(counts['assigned'].sum()),
                           'true_useful_pulses':int(counts['true_useful'].sum()),'empty_angle_bins':int((counts['assigned']==0).sum())}}
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/experiments/scan/from-system')
def scan_from_system(config: dict):
    try:
        a=Algorithms.load()
        from ..experiments.system_config import form_values
        source=form_values(SimulationConfig.for_experiment('system',config,a))
        source['timing'].pop('laser_shots')
        source['timing'].pop('monte_carlo_trials',None)
        result=SimulationConfig.for_experiment('scan',source,a)
        return {'schema_version':3,'kind':'scan','experiment':result.model_dump(),
                'note':'已继承B的器件、光学、读出、时序与seed；C的发数由扫描帧预算重新生成，不继承B的累计发数。'}
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/jobs/{job_id}/scan-replay')
def replay_scan(job_id: str, request: ReplayRequest):
    try:
        from ..processing.scan_reconstruction import reconstruct_scan
        result=manager().result(job_id)
        if 'scan' not in result:
            raise ValueError('This result is not a scanning acquisition')
        original=result['record_schema']['tdc_bin_ps']
        ratio=request.bin_ps/original
        if request.bin_ps<original or not np.isclose(ratio,round(ratio),rtol=0,atol=np.finfo(float).eps*max(1,ratio)):
            raise ValueError('Replay bin must be an integer multiple of acquisition resolution')
        a=Algorithms.from_snapshot(result['configuration']['algorithms'])
        cfg=SimulationConfig.for_experiment('scan',result['configuration']['experiment'],a)
        s=result['scan'];truth={int(k):{name:np.asarray(v) for name,v in row.items()} for k,row in s['source_truth_by_cycle'].items()}
        return reconstruct_scan(cfg,a,result['records'],s['warmup_schedule']+s['schedule'],np.array(s['angle_edges_mrad']),
                                s['channel_directions_mrad'],truth,request.bin_ps)
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.get('/api/jobs/{job_id}/point-cloud.csv')
def point_cloud_csv(job_id: str, bin_ps: float | None = None):
    try:
        import csv,io
        result=manager().result(job_id)
        reconstruction=result['scan'] if bin_ps is None else replay_scan(job_id,ReplayRequest(bin_ps=bin_ps))
        rows=[{**row,'processing_bin_ps':reconstruction['processing_bin_ps']} for row in reconstruction['point_cloud']]
        fields=['frame','angle_bin','channel','x_m','y_m','z_m','raw_distance_m','reported_h_mrad','reported_v_mrad','assigned_pulses','recorded_counts','status','processing_bin_ps']
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
        return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{job_id}-point-cloud.csv"'})
    except (ValueError,KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/experiments/{kind}/import')
def import_experiment(kind: str, document: str = Body(media_type='text/plain')):
    try:
        envelope = parse_yaml(document)
        allowed=(2,3) if kind in ('system','scan') else (2,)
        if set(envelope) != {'schema_version', 'kind', 'experiment'} or envelope['schema_version'] not in allowed or envelope['kind'] != kind:
            raise ValueError('Expected a supported schema_version and matching experiment kind; legacy A uses its own import entry')
        return SimulationConfig.for_experiment(kind, envelope['experiment']).model_dump()
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/experiments/{kind}/form')
def system_form(kind:str,config:dict):
    from ..experiments.system_config import form_values
    try:
        if kind not in ('system','scan'):raise ValueError('Expected system or scan workspace')
        cfg=SimulationConfig.for_experiment(kind,config)
        return {'configuration':cfg.model_dump(),'form':form_values(cfg)}
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/experiments/system/preview')
def system_preview(config:dict):
    from ..experiments.spatial import project_illumination
    from ..experiments.lab import stamp_result
    from ..reporting.spatial_view import optical_view
    try:
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('system',config,a)
        light,groups,optics=project_illumination(cfg,a,lambda *args:None,lambda:False)
        view=optical_view(cfg,a,optics)
        view.update(optics=optics,illumination={'signal_photons_per_pixel_per_pulse':light.signal_photons_per_pulse.sum(axis=1).tolist(),
                                              'shape':optics['array_shape']})
        return stamp_result('B_parameter_preview_without_event_sampling',cfg,a,view)
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/experiments/scan/workspace-preview')
def scan_workspace_preview(config:dict):
    from ..experiments.spatial import project_illumination
    from ..experiments.lab import stamp_result
    from ..reporting.spatial_view import optical_view
    from ..scan.schedule import build_schedule
    from ..spad.device import effective_pde
    from ..curves import Curve
    try:
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('scan',config,a)
        schedule=preview_scan(config)
        light,groups,optics=project_illumination(cfg,a,lambda *args:None,lambda:False)
        view=optical_view(cfg,a,optics,laser_shots=schedule['summary']['emitted_reference_slots'])
        program,_,_,_=build_schedule(cfg,a)
        exposure=sum((w.end_ns-w.start_ns) if cfg.device.detector_operation=='free_running' else (w.gate_close_ns-w.gate_open_ns) for w in program.windows)*1e-9
        optical_noise=light.background_photons_per_second@effective_pde(Curve(cfg.spectral_inputs.pde)(light.wavelength_nm),cfg.device.fill_factor)
        noise=float((optical_noise+cfg.device.dcr_cps_per_spad+cfg.device.other_noise_cps_per_spad).sum()*exposure)
        view.update(scan_preview=schedule,optics=optics,illumination={'signal_photons_per_pixel_per_pulse':light.signal_photons_per_pulse.sum(axis=1).tolist(),'shape':optics['array_shape']},
            resource_probe={'expected_noise_candidates':noise,'event_limit':a.max_readout_events_per_run,'blocked':noise>a.max_readout_events_per_run,
                            'note':'仅背景/器件噪声候选下界，包含预热；信号候选另计。超限不自动降低背景或发数。'})
        view['parameter_figures']['pulse']['facts'][1][0]='连续PRF平均功率参考'
        return stamp_result('C_schedule_and_static_optics_preview_without_event_sampling',cfg,a,view)
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.get('/api/experiments/scan/demo')
def scan_demo():
    try:
        return SimulationConfig.for_experiment('scan',read_yaml('defaults.yaml')['experiments']['scan_demo']).model_dump()
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/jobs/{job_id}/scan-view')
def scan_result_view(job_id:str):
    from ..reporting.spatial_view import optical_view
    try:
        result=manager().result(job_id)
        if 'scan' not in result:raise ValueError('Expected a C scan result')
        if result['optics']['dataset']['coordinate_convention'].endswith('y_down'):
            result['view_note']='历史结果保留原坐标定义及原始记录；用于新坐标标定前，请迁移配置并重新采集。'
        a=Algorithms.from_snapshot(result['configuration']['algorithms'])
        cfg=SimulationConfig.for_experiment('scan',result['configuration']['experiment'],a)
        result.update(optical_view(cfg,a,result['optics'],laser_shots=result['scan']['summary']['emitted_reference_slots']))
        emitted=result['scan']['summary']['emitted_reference_slots']
        result['display_summary']={'mean_sensor_photons_per_emitted_pulse':float(np.asarray(result['illumination']['signal_photons_per_pixel_per_pulse']).sum()) if emitted else None,
                                   'normalization':'Actual measured emitted reference slots; no value when none were emitted.'}
        result['parameter_figures']['pulse']['facts'][1][0]='连续PRF平均功率参考'
        return result
    except (ValueError,KeyError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc

"""Formal column-C read-only planning, job views and exports."""
from pathlib import Path
from hashlib import sha256
import csv,io,json
from collections import OrderedDict
from threading import Lock
from typing import Annotated
from fastapi import APIRouter,HTTPException,Body
from fastapi.responses import HTMLResponse,Response
from pydantic import BaseModel,ConfigDict,Field
from ..configuration import Algorithms,read_yaml,parse_yaml
from ..models import SimulationConfig
from ..runtime.jobs import manager
from ..reporting.column_view import column_preview,system_budget_view,motion_view,selected_histogram
from ..scan.column_schedule import build_column_schedule

router=APIRouter();WEB=Path(__file__).resolve().parents[3]/'web'
_results=OrderedDict();_result_lock=Lock()


def column_page():
    html=(WEB/'columns.html').read_text(encoding='utf8')
    for name in ('columns.css','columns.js','shared/column-layout.css','shared/plot-series.js',
                 'shared/histogram-window.js','curve-editor.js','vendor/katex/katex.min.js','vendor/katex/katex.min.css'):
        html=html.replace(f'/static/{name}"',f'/static/{name}?v={sha256((WEB/name).read_bytes()).hexdigest()}"')
    return HTMLResponse(html)


@router.get('/system/columns')
def columns_page():return column_page()


@router.get('/api/columns')
def catalog():
    cfg=SimulationConfig.for_experiment('columns',{})
    curves=read_yaml('curve-inputs.yaml');curves.update(formulas=read_yaml('formulas.yaml'),formula_notes=read_yaml('formula-notes.yaml'))
    return {'defaults':cfg.model_dump(),'schema':type(cfg).model_json_schema(),'help':read_yaml('parameter-help.yaml'),
        'algorithms':Algorithms.load().model_dump(),'curves':curves,'readout_modes':read_yaml('readout-modes.yaml'),
        'schema_version':4,'kind':'columns'}


@router.post('/api/columns/budget')
def budget(config:dict):
    return system_budget_view(SimulationConfig.system_targets(config))


@router.post('/api/columns/preview')
def preview(config:dict,column_id:int=0):
    try:
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('columns',config,a)
        return column_preview(cfg,a,column_id)
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@router.post('/api/columns/plan')
def plan(config:dict,column_id:int=0):
    try:
        from ..scan.transport import transport_plan
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('columns',config,a)
        p,rows,cols,b=build_column_schedule(cfg,a)
        if not 0<=column_id<len(cols):raise ValueError('Unknown column')
        return {'configuration':cfg.model_dump(),'system_budget':system_budget_view(cfg.system_targets),
                'columns':cols,'schedule':[r for r in rows if r['measured']],'frame_budget':b,
                'motion':motion_view(cfg,a,rows,column_id),'transport':transport_plan(cfg,cols)}
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/columns/demo')
def demo():return SimulationConfig.for_experiment('columns',read_yaml('defaults.yaml')['experiments']['scan_demo']).model_dump()


class SystemTransfer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    system:dict
    current:dict


@router.post('/api/columns/from-system')
def from_system(request:SystemTransfer):
    from ..scan.column_config import column_defaults
    from ..curves import merge_config
    b=SimulationConfig.for_experiment('system',request.system).model_dump()
    values=merge_config(column_defaults(),request.current)
    for group in ('tx','scene','rx','spad','readout','background','spectral_inputs'):values[group]=b[group]
    values['acquisition']['calibration_delay_ns']=b['acquisition']['calibration_delay_ns']
    cfg=SimulationConfig.for_experiment('columns',values)
    return {'schema_version':4,'kind':'columns','experiment':cfg.model_dump()}


@router.post('/api/columns/import')
def import_config(document:str=Body(media_type='text/plain')):
    try:
        envelope=parse_yaml(document)
        if set(envelope)!={'schema_version','kind','experiment'} or envelope['schema_version']!=4 or envelope['kind']!='columns':
            raise ValueError('Expected a schema_version 4 columns configuration')
        return SimulationConfig.for_experiment('columns',envelope['experiment']).model_dump()
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


def saved(job_id):
    record=manager().get(job_id)
    if record['status']!='completed':raise ValueError('Acquisition has not completed')
    path=Path(record['result_path']);stat=path.stat();key=(job_id,stat.st_mtime_ns,stat.st_size)
    limit=Algorithms.load().column_result_cache_entries
    with _result_lock:
        if key in _results:result=_results.pop(key)
        else:result=manager().result(job_id)
        if limit:_results[key]=result
        while len(_results)>limit:_results.popitem(last=False)
    if 'column_scan' not in result:raise ValueError('This is not a column-C acquisition')
    a=Algorithms.from_snapshot(result['configuration']['algorithms'])
    cfg=SimulationConfig.for_experiment('columns',result['configuration']['experiment'],a)
    return result,cfg,a


@router.get('/api/columns/jobs/{job_id}/view')
def result_view(job_id:str,frame:int|None=None):
    try:
        result,cfg,a=saved(job_id)
        if frame is None:frame=result['column_scan']['columns'][0]['frame']
        if not 0<=frame<cfg.acquisition.frame_count:raise ValueError('Unknown frame')
        scan=result['column_scan'];n=cfg.system_targets.slot_count;channels=cfg.spad.channels_h*cfg.spad.channels_v
        counts=[[None]*n for _ in range(channels)];ranges=[[None]*n for _ in range(channels)]
        for row in scan['range_rows']:
            if row['frame']==frame:counts[row['channel']][row['column']]=row['recorded_counts'];ranges[row['channel']][row['column']]=row['raw_distance_m']
        audit={k:v for k,v in result['audit'].items() if k!='source'}
        audit['source']={k:v for k,v in result['audit']['source'].items() if k!='expected_signal_candidates_by_cycle'}
        statistics={k:v for k,v in result['statistics'].items() if k not in ('trial_records','noise_records')}
        return {'configuration':result['configuration'],'provenance':result['provenance'],'audit':audit,
            'summary':scan['summary'],'transport':scan['transport'],'frame_budget':scan['frame_budget'],
            'counts':counts,'ranges':ranges,'point_cloud':[p for p in scan['point_cloud'] if p['frame']==frame],
            'statistics':statistics,'frame':frame,'measured_column_ids':scan['measured_column_ids'],
            'first_column':next((c['column'] for c in scan['columns'] if c['frame']==frame),None),
            'photon_flow':result['photon_flow'],'limitations':result['limitations']}
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


class HistogramRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    column_id:int=Field(ge=0,strict=True)
    channels:list[Annotated[int,Field(ge=0,strict=True)]]
    bin_ps:float=Field(gt=0)
    include_reference:bool


@router.post('/api/columns/jobs/{job_id}/histogram')
def histogram(job_id:str,request:HistogramRequest):
    try:
        result,cfg,a=saved(job_id)
        return selected_histogram(result,cfg,a,request.column_id,request.channels,request.bin_ps,request.include_reference)
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/columns/jobs/{job_id}/records.csv')
def records_csv(job_id:str):
    try:
        result,_,_=saved(job_id);fields=['frame','column','column_id','cycle','pulse_reference','channel','tdc','tdc_code','time_ns','phase_ns','interval_start_ns','interval_end_ns']
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(result['records'])
        return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{job_id}-records.csv"'})
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/columns/jobs/{job_id}/point-cloud.csv')
def points_csv(job_id:str,delivered:bool=False):
    try:
        result,_,_=saved(job_id);key='delivered_point_cloud' if delivered else 'point_cloud';rows=result['column_scan'][key]
        if rows is None:raise ValueError('Transport was not configured; delivered point cloud is undefined')
        fields=['frame','column','column_id','h_route','v_line','channel','x_m','y_m','z_m','raw_distance_m','recorded_counts','status']
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
        return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{job_id}-points.csv"'})
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc

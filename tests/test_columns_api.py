import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.curves import merge_config
from spad_lidar.experiments.columns import run_columns
from spad_lidar.processing.column_reconstruction import histogram_edges,histogram_bin_count


def test_formal_route_defaults_and_independent_budget():
    c=TestClient(app);page=c.get('/system/scan')
    assert 'data-lab="columns"' in page.text
    for name in ('columns.js','columns.css','shared/histogram-window.js','shared/plot-series.js','curve-editor.js'):
        assert f'/static/{name}?v=' in page.text
    d=c.get('/api/columns').json()
    assert d['defaults']['system_targets']==dict(frame_rate_hz=10,hfov_deg=120,scan_time_utilization=.667,slot_count=1000)
    budget=c.post('/api/columns/budget',json={'frame_rate_hz':100}).json()
    assert budget['derived']['slot_target_ns']==pytest.approx(6670)
    assert c.post('/api/columns/preview',json={'system_targets':{'frame_rate_hz':100}}).status_code==422
    assert c.post('/api/columns/budget',json={'hfov_mrad':120}).status_code==422


def test_local_experiment_retains_system_targets_and_background():
    c=TestClient(app)
    out=c.post('/api/columns/preview?column_id=7',json={'acquisition':{'scope_mode':'columns','scope_first_column':7,'scope_column_count':2}})
    assert out.status_code==200
    v=out.json();cfg=v['configuration']['experiment']
    assert cfg['background']['solar_enabled'] and cfg['background']['other_light_enabled']
    assert cfg['system_targets']['slot_count']==1000
    assert v['resource_probe']['measured_columns']==2 and not v['resource_probe']['blocked']
    assert 'records' not in v


def test_system_transfer_retains_column_requirements():
    c=TestClient(app)
    r=c.post('/api/columns/from-system',json={'system':{'scene':{'range_m':120}},'current':{'system_targets':{'hfov_deg':90}}})
    assert r.status_code==200
    v=r.json()['experiment']
    assert v['system_targets']['hfov_deg']==90 and v['scene']['range_m']==120
    assert len(v['exposure']['pulses'])==4


def test_decimal_histogram_grid_has_no_duplicate_endpoint():
    cfg=SimulationConfig.for_experiment('columns',{'acquisition':{'gate_start_ns':.1,'gate_width_ns':.3},'readout':{'tdc_bin_ps':100}})
    edges=histogram_edges(cfg,100)
    assert len(edges)-1==histogram_bin_count(cfg,100)==4
    assert np.all(np.diff(edges)>0) and edges[-1]==pytest.approx(.4)


@pytest.fixture
def acquisition():
    settings=merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{
        'system_targets':{'slot_count':4},'acquisition':{'trial_count':3,'noise_trial_count':2}})
    cfg=SimulationConfig.for_experiment('columns',settings)
    return run_columns(cfg,Algorithms.load(),lambda *args:None,lambda:False)


def test_job_view_replay_export_and_statistics(acquisition,tmp_path,monkeypatch):
    import spad_lidar.webapi.columns as api
    path=tmp_path/'result.json';path.write_text(json.dumps(acquisition,allow_nan=False),encoding='utf8')
    class Saved:
        def get(self,job_id):return {'status':'completed','result_path':str(path)}
        def result(self,job_id):return acquisition
    monkeypatch.setattr(api,'manager',lambda:Saved())
    c=TestClient(app)
    view=c.get('/api/columns/jobs/test/view').json()
    assert view['summary']['column_count']==4 and len(view['counts'])==32
    assert 'trial_records' not in view['statistics']
    h=c.post('/api/columns/jobs/test/histogram',json={'column_id':0,'channels':[14,15],'bin_ps':2000,'include_reference':True})
    assert h.status_code==200
    v=h.json();assert v['statistics']['trial_count']==3 and v['statistics']['noise_trial_count']==2
    assert v['statistics']['lower'] is not None and v['statistics']['noise_mean'] is not None
    assert len(v['references'])==2 and np.asarray(v['references'][0]['counts']).min()>=0
    assert c.post('/api/columns/jobs/test/histogram',json={'column_id':0,'channels':[14,14],'bin_ps':2000,'include_reference':False}).status_code==422
    assert c.post('/api/columns/jobs/test/histogram',json={'column_id':0,'channels':[14],'bin_ps':1500,'include_reference':False}).status_code==422
    assert 'column_id' in c.get('/api/columns/jobs/test/records.csv').text.splitlines()[0]
    assert c.get('/api/columns/jobs/test/point-cloud.csv').status_code==200


def test_bright_two_column_acquisition_is_explicit_and_bounded():
    cfg=SimulationConfig.for_experiment('columns',{'acquisition':{'scope_mode':'columns','scope_first_column':7,'scope_column_count':2}})
    r=run_columns(cfg,Algorithms.load(),lambda *args:None,lambda:False)
    assert r['column_scan']['measured_column_ids']==[7,8]
    assert all(x['column_id'] in (7,8) for x in r['records'])
    assert r['column_scan']['summary']['column_count']==2
    assert r['column_scan']['frame_budget']['column_count']==1000
    assert r['audit']['source']['expected_work']<Algorithms.load().max_readout_events_per_run
    assert r['configuration']['experiment']['background']['solar_enabled']

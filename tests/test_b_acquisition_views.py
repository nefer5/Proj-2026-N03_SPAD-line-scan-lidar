from copy import deepcopy
from types import SimpleNamespace
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.experiments.spatial_analysis import run_system_analysis
from spad_lidar.reporting.b_acquisition import acquisition_context,histogram_scope_view,spatial_scope_values
from spad_lidar.runtime.result_views import cached_result


@pytest.fixture(scope='module')
def different_n_m():
    cfg=SimulationConfig.for_experiment('system',{
        'acquisition':{'laser_shots':3,'monte_carlo_trials':5},
        'background':{'solar_enabled':False,'other_light_enabled':False}})
    a=Algorithms.load()
    result=run_system_analysis(cfg,a,lambda *args:None,lambda:False)
    return cfg,a,result


def test_n_and_m_have_separate_meaning_and_gate_sum_is_slot(different_n_m):
    cfg,a,result=different_n_m;channels=[14,15,16,17];before=deepcopy(result)
    context=acquisition_context(cfg,a,result['optics'],result=result)
    assert context['shots']==3 and context['trial_count']==5
    assert context['sequence_duration_ns']==3*cfg.timing.period_ns
    historical={k:v for k,v in result.items() if k!='statistics'}
    assert acquisition_context(cfg,a,result['optics'],result=historical)['trial_count'] is None
    assert context['independent_slot_budget_ns'] is None
    folded=histogram_scope_view(result,cfg,a,'slot',0,cfg.readout.tdc_bin_ps,channels)
    separate=[histogram_scope_view(result,cfg,a,'gate',k,cfg.readout.tdc_bin_ps,channels) for k in range(3)]
    for ch in channels:
        assert np.array_equal(np.sum([v['histogram']['counts'][ch] for v in separate],axis=0),result['histogram']['counts'][ch])
        assert folded['histogram']['counts'][ch]==result['histogram']['counts'][ch]
        for k,view in enumerate(separate):
            assert view['record_counts'][ch]==sum(r['channel']==ch and r['cycle']==k for r in result['records'])
            assert view['statistics'] is None  # no false division of MC extrema
            assert view['shots_in_view']==1
            assert np.allclose(view['references'][ch]['counts'],np.asarray(folded['references'][ch]['counts'])/3)
            assert view['noise_reference']['counts_per_bin'][ch]==pytest.approx(folded['noise_reference']['counts_per_bin'][ch]/3)
    assert folded['statistics']['trial_count']==5
    assert result==before


def test_scope_rebin_preserves_counts_and_recomputes_folded_extrema(different_n_m):
    cfg,a,result=different_n_m;channels=[15,16]
    view=histogram_scope_view(result,cfg,a,'slot',0,2*cfg.readout.tdc_bin_ps,channels)
    trials=np.asarray(result['statistics']['trial_histograms'])
    expected=np.add.reduceat(trials,np.arange(0,trials.shape[-1],2),axis=-1)
    for ch in channels:
        assert view['statistics']['upper'][ch]==expected[:,ch].max(axis=0).tolist()
        assert view['statistics']['lower'][ch]==expected[:,ch].min(axis=0).tolist()
        assert view['record_counts'][ch]==sum(r['channel']==ch for r in result['records'])
    with pytest.raises(ValueError):histogram_scope_view(result,cfg,a,'gate',3,cfg.readout.tdc_bin_ps,channels)
    with pytest.raises(ValueError):histogram_scope_view(result,cfg,a,'slot',0,cfg.readout.tdc_bin_ps/2,channels)
    with pytest.raises(ValueError):histogram_scope_view(result,cfg,a,'slot',0,cfg.readout.tdc_bin_ps,[15,15])
    with pytest.raises(ValueError,match='reference'):
        histogram_scope_view(result,cfg,a.model_copy(update={'max_lab_reference_cells':1}),'slot',0,cfg.readout.tdc_bin_ps,channels)


def test_grouped_timeline_preserves_all_gates_and_photon_scope(different_n_m):
    cfg,a,result=different_n_m
    a=a.model_copy(update={'b_timeline_max_points':2,'b_mechanism_preview_gates':1})
    view=histogram_scope_view(result,cfg,a,'gate',1,cfg.readout.tdc_bin_ps,[15,16]);timeline=view['timeline']
    assert timeline['grouped'] and timeline['start_gate']==[0,1] and timeline['end_gate']==[0,2]
    for i,ch in enumerate(timeline['channels']):
        assert timeline['cumulative_counts'][i][-1]==sum(result['histogram']['counts'][ch])
    scopes=spatial_scope_values(result['illumination'],cfg.timing.laser_shots)
    assert np.array_equal(scopes['slot']['signal_photons_per_pixel'],np.asarray(scopes['per_pulse']['signal_photons_per_pixel'])*3)
    ctx=acquisition_context(cfg,a,result['optics'],result=result)
    assert ctx['gate_preview_truncated'] and len(ctx['gate_preview'])==1
    assert ctx['gate_preview_end_ns']==cfg.timing.period_ns


def test_endpoint_enums_and_immutable_file_cache(different_n_m,tmp_path,monkeypatch):
    from spad_lidar.webapi import labs
    cfg,a,result=different_n_m;path=tmp_path/'result.json';path.write_text(json.dumps(result),encoding='utf-8')
    fake=SimpleNamespace(get=lambda job:{'status':'completed','result_path':str(path)})
    monkeypatch.setattr(labs,'manager',lambda:fake)
    client=TestClient(app);payload={'scope':'gate','gate_index':1,'bin_ps':cfg.readout.tdc_bin_ps,'channels':[15]}
    response=client.post('/api/jobs/view-test/system-histogram',json=payload)
    assert response.status_code==200 and response.json()['gate_index']==1
    for change in [{'scope':'bad'},{'gate_index':True},{'gate_index':-1},{'channels':[999]},{'channels':[]},{'bin_ps':0}]:
        assert client.post('/api/jobs/view-test/system-histogram',json={**payload,**change}).status_code==422
    first=cached_result(fake,'view-test',2);assert cached_result(fake,'view-test',2) is first
    second={**result,'view_marker':'updated'};path.write_text(json.dumps(second),encoding='utf-8')
    assert cached_result(fake,'view-test',2)['view_marker']=='updated'
    assert cached_result(fake,'view-test',0) is not cached_result(fake,'view-test',0)

import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.performance import performance_sweep
from spad_lidar.simulator import simulate


def test_sweep_point_matches_standalone_same_seed_and_mode():
    cfg=SimulationConfig(readout_mode='shared_multi',monte_carlo_trials=2)
    sweep=performance_sweep(cfg,'range_m',[75,100])
    for point in sweep['points']:
        run=simulate(SimulationConfig(**{**cfg.model_dump(),'range_m':point['value'],'rng_seed':point['seed']}))
        assert point['mode']=='shared_multi'
        assert point['engine']=='event_monte_carlo'
        assert point['pd']==run['detection']['pd']
        assert point['pfa']==run['detection']['pfa']
        assert point['precision_cm_1sigma']==run['metrics']['precision_cm_1sigma']
        assert point['configuration_sha256']==run['provenance']['sha256']


@pytest.mark.parametrize('axis,values',[('solar_illuminance_lux',[0,50000]),('laser_shots',[1,2])])
def test_supported_axes_and_reproducibility(axis,values):
    cfg=SimulationConfig(monte_carlo_trials=1)
    first=performance_sweep(cfg,axis,values)
    second=performance_sweep(cfg,axis,values)
    assert first==second
    if axis=='solar_illuminance_lux':
        assert first['points'][0]['background_candidates_per_gate']<first['points'][1]['background_candidates_per_gate']
    else:
        assert first['points'][1]['ideal_signal_candidates']==pytest.approx(2*first['points'][0]['ideal_signal_candidates'])


def test_sweep_rejects_invalid_or_overbudget_batches_before_running(monkeypatch):
    cfg=SimulationConfig()
    for axis,values in [('range_m',[10000]),('laser_shots',[1.5]),('range_m',[1,1])]:
        with pytest.raises(ValueError):performance_sweep(cfg,axis,values)
    with pytest.raises(ValueError):performance_sweep(SimulationConfig(monte_carlo_trials=0),'range_m',[100])
    a=Algorithms.load().model_copy(update={'max_performance_sweep_bin_work':1})
    monkeypatch.setattr(Algorithms,'load',classmethod(lambda cls:a))
    with pytest.raises(ValueError,match='Whole sweep'):performance_sweep(cfg,'range_m',[100])


def test_sweep_api_validates_and_returns_selected_engine():
    c=TestClient(app)
    payload={'configuration':{'readout_mode':'analytic_reference','monte_carlo_trials':1},'axis':'range_m','values':[100]}
    response=c.post('/api/performance-sweep',json=payload)
    assert response.status_code==200
    assert response.json()['points'][0]['engine']=='analytic_multinomial'
    payload['values']=[-1]
    assert c.post('/api/performance-sweep',json=payload).status_code==422

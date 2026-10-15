import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.simulator import simulate, photon_budget
from spad_lidar.experiments import a_acquisition


def test_defaults_and_independent_import_export():
    client=TestClient(app)
    defaults=client.get('/api/defaults').json()
    keys=('monte_carlo_trials','readout_mean_trials','noise_mean_trials')
    assert [defaults[k] for k in keys]==[4,8,6]
    config=SimulationConfig(monte_carlo_trials=2,readout_mean_trials=3,noise_mean_trials=7)
    exported=client.post('/api/config/export',json=config.model_dump())
    imported=client.post('/api/config/import',content=exported.text,headers={'Content-Type':'text/plain'})
    assert imported.status_code==200
    assert [imported.json()[k] for k in keys]==[2,3,7]
    # Old partial user configs adopt new YAML defaults for newly introduced keys.
    legacy=client.post('/api/config/import',content='monte_carlo_trials: 4',headers={'Content-Type':'text/plain'})
    assert legacy.json()['monte_carlo_trials']==4
    assert legacy.json()['readout_mean_trials']==defaults['readout_mean_trials']
    assert legacy.json()['noise_mean_trials']==defaults['noise_mean_trials']


@pytest.mark.parametrize('key',['readout_mean_trials','noise_mean_trials'])
@pytest.mark.parametrize('value',[0,-1,1.5,float('nan'),float('inf'),True,'3'])
def test_mean_counts_reject_invalid_values(key,value):
    with pytest.raises(ValueError):SimulationConfig(**{key:value})


def test_mean_count_resource_bound_and_unknown_key():
    for key in ('readout_mean_trials','noise_mean_trials'):
        with pytest.raises(ValueError,match='resource limit'):
            SimulationConfig(**{key:Algorithms.load().max_monte_carlo_trials+1})
    with pytest.raises(ValueError):SimulationConfig(noise_mean_trial=3)


def test_each_mean_uses_its_own_denominator_and_exact_number_of_batches(monkeypatch):
    calls={'signal':0,'noise':0}
    def sample(cfg,budget,rng,algorithms,edges,signal=True,trace=False):
        key='signal' if signal else 'noise';calls[key]+=1
        return np.array([calls[key]*(1 if signal else 2)],dtype=float),{'logic_triggers':0},[]
    monkeypatch.setattr(a_acquisition,'event_histogram',sample)
    cfg=SimulationConfig(monte_carlo_trials=2,readout_mean_trials=3,noise_mean_trials=4)
    observed,expected,noise,trials,meta=a_acquisition.event_acquisition(cfg,photon_budget(cfg),Algorithms.load(),np.array([0,1]))
    assert calls=={'signal':5,'noise':4}
    assert observed.tolist()==[1]
    assert expected.tolist()==[3]  # mean of 2,3,4
    assert noise.tolist()==[5]  # mean of 2,4,6,8
    assert [x.tolist() for x in trials]==[[1],[5]]
    assert meta['expected_trials']==3 and meta['noise_mean_trials']==4
    work=meta['work_estimate']
    assert work['signal_runs']==5 and work['noise_runs']==4
    assert work['cycles']==9*cfg.laser_shots
    assert meta['warmup_cycles']==0 and meta['initial_condition']=='fully_recovered'


def test_mean_counts_do_not_change_other_random_streams_or_analytic_gt():
    cfg=SimulationConfig(monte_carlo_trials=3,readout_mean_trials=2,noise_mean_trials=4)
    baseline=simulate(cfg)
    changed_signal=simulate(SimulationConfig(**(cfg.model_dump()|{'readout_mean_trials':5})))
    changed_noise=simulate(SimulationConfig(**(cfg.model_dump()|{'noise_mean_trials':7})))
    for result in (changed_signal,changed_noise):
        for key in ('observed_counts','sample_range','ground_truth'):
            assert baseline['histogram'][key]==result['histogram'][key]
    assert baseline['histogram']['expected_noise_counts']==changed_signal['histogram']['expected_noise_counts']
    assert baseline['histogram']['expected_counts']==changed_noise['histogram']['expected_counts']


def test_zero_mc_still_includes_one_observation_in_work_estimate():
    cfg=SimulationConfig(monte_carlo_trials=0,readout_mean_trials=2,noise_mean_trials=4)
    work=a_acquisition.readout_work_estimate(cfg,photon_budget(cfg),Algorithms.load())
    assert work['signal_runs']==3 and work['noise_runs']==4

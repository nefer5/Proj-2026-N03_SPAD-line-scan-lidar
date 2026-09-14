import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import histogram_sample_range, simulate
from spad_lidar import simulator


def test_sample_extrema_are_per_bin_without_filtering_or_averaging():
    samples=[np.array([0,5,1]),np.array([3,1,1]),np.array([2,2,0])]
    result=histogram_sample_range(samples)
    assert result['lower_counts']==[0,1,0]
    assert result['upper_counts']==[3,5,1]
    assert result['trial_count']==3
    assert samples[0].tolist()==[0,5,1]
    assert histogram_sample_range([])['lower_counts'] is None


@pytest.mark.parametrize('mode',['independent_multi','analytic_reference'])
def test_first_observation_is_preserved_and_included_in_ranges(mode):
    common=dict(readout_mode=mode,laser_shots=1)
    results=[simulate(SimulationConfig(**common,monte_carlo_trials=n),debug=True) for n in (0,1,4)]
    first=results[0]['histogram']['observed_counts']
    for n,result in zip((0,1,4),results):
        h=result['histogram'];bounds=h['sample_range']
        assert h['observed_counts']==first
        assert bounds['trial_count']==n
        assert result['metrics']['trials_completed']==n
        assert len(result['debug']['trial_estimates_m'])==n
        assert bounds['available']==bool(n)
        if n:
            assert np.all(np.asarray(bounds['lower_counts'])<=first)
            assert np.all(np.asarray(bounds['upper_counts'])>=first)
            assert result['debug']['trial_estimates_m'][0]==result['metrics']['estimated_range_m']
        else:
            assert bounds['lower_counts'] is None and bounds['upper_counts'] is None
    assert results[1]['histogram']['sample_range']['lower_counts']==first
    assert results[1]['histogram']['sample_range']['upper_counts']==first


def test_ranges_reuse_exact_distance_statistics_histograms(monkeypatch):
    actual=simulator.event_acquisition
    captured={}
    def capture(*args,**kwargs):
        result=actual(*args,**kwargs)
        captured['samples']=result[3]
        return result
    monkeypatch.setattr(simulator,'event_acquisition',capture)
    result=simulate(SimulationConfig(monte_carlo_trials=5,laser_shots=1))
    samples=np.asarray(captured['samples'])
    assert result['histogram']['sample_range']['lower_counts']==samples.min(axis=0).tolist()
    assert result['histogram']['sample_range']['upper_counts']==samples.max(axis=0).tolist()
    assert samples[0].tolist()==result['histogram']['observed_counts']

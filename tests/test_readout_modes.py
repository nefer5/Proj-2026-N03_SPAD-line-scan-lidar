import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.readout import route_events
from spad_lidar.simulator import simulate
from spad_lidar.configuration import read_yaml


def config(mode,**kwargs):
    parameters=dict(readout_mode=mode,range_m=20,laser_shots=2,
                    laser_prf_hz=1000000,gate_start_ns=0,gate_width_ns=700,
                    tdc_bin_ps=100,monte_carlo_trials=0)
    parameters.update(kwargs)
    return SimulationConfig(**parameters)


def test_independent_single_vs_multi_and_spad_deadtime():
    times=[10,15,40];pixels=[0,0,0]
    first=route_events(config('independent_first'),times,pixels)
    multi=route_events(config('independent_multi'),times,pixels)
    assert first[0].tolist()==[10]
    assert multi[0].tolist()==[10,40]
    assert first[1]['spad_dead_losses']==1
    assert first[1]['capacity_losses']==1


def test_tdc_rejection_still_rearms_spad_deadtime():
    result=route_events(config('independent_multi',spad_dead_time_ns=20,tdc_dead_time_ns=50),
                        [10,40,55,70],[0,0,0,0])
    assert result[0].tolist()==[10,70]
    assert result[1]['tdc_dead_losses']==1
    assert result[1]['spad_dead_losses']==1


def test_or_union_merges_overlapping_pulses():
    cfg=config('shared_multi',or_pulse_width_ns=1,tdc_dead_time_ns=0)
    result=route_events(cfg,[10,10.5,11.2,13],[0,1,2,3])
    assert result[0].tolist()==[10,13]
    assert result[1]['logic_rejected_or_merged']==2
    assert route_events(config('shared_first',or_pulse_width_ns=1,tdc_dead_time_ns=0),[10,13],[0,1])[0].tolist()==[10]


def test_multiple_tdcs_and_capacity():
    times=[10,12,14,30]; pixels=[0,1,2,3]
    cfg=config('shared_multitdc',tdc_count=2,or_pulse_width_ns=0,tdc_dead_time_ns=10)
    assert route_events(cfg,times,pixels)[0].tolist()==[10,12,30]
    cfg=config('shared_multi',tdc_max_hits_per_cycle=1,or_pulse_width_ns=0,tdc_dead_time_ns=0)
    assert route_events(cfg,times,pixels)[0].tolist()==[10]


def test_coincidence_timestamp_conventions_and_distinct_cells():
    fixed=config('coincidence_fixed',coincidence_window_ns=4,coincidence_threshold=2,tdc_dead_time_ns=0)
    sliding=config('coincidence_sliding',coincidence_window_ns=4,coincidence_threshold=2,tdc_dead_time_ns=0)
    assert route_events(fixed,[10,11],[0,1])[0]==pytest.approx([12])
    assert route_events(sliding,[10,11],[0,1])[0].tolist()==[11]
    same=config('coincidence_sliding',spad_dead_time_ns=0,coincidence_threshold=2)
    assert len(route_events(same,[10,11],[0,0])[0])==0
    assert route_events(sliding,[10,11,15,16],[0,1,2,3])[0].tolist()==[11,16]


def test_outside_gate_events_and_cross_period_deadtime():
    gated=config('independent_multi',gate_start_ns=100,gate_width_ns=300,detector_operation='gated')
    free=config('independent_multi',gate_start_ns=100,gate_width_ns=300,detector_operation='free_running')
    assert route_events(gated,[95,105],[0,0])[0].tolist()==[105]
    assert len(route_events(free,[95,105],[0,0])[0])==0
    long_dead=config('independent_multi',spad_dead_time_ns=400)
    assert route_events(long_dead,[695,1005,1100],[0,0,0])[0].tolist()==[695,100]


@pytest.mark.parametrize('mode',list(read_yaml('readout-modes.yaml')))
def test_every_mode_produces_reproducible_histograms(mode):
    cfg=config(mode)
    a=simulate(cfg,debug=True);b=simulate(cfg)
    assert a['histogram']==b['histogram']
    assert a['readout']['mode']==mode
    assert np.all(np.isfinite(a['histogram']['expected_counts']))

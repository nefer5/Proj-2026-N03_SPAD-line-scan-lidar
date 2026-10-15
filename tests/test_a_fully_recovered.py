import numpy as np
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.simulator import photon_budget, simulate
from spad_lidar.experiments import a_acquisition
from spad_lidar.readout import route_events


def test_no_warmup_cycles_are_sampled_even_if_legacy_policy_is_nonzero(monkeypatch):
    cfg=SimulationConfig(laser_shots=3,monte_carlo_trials=0,
                         spad_jitter_fwhm_ps=0,other_jitter_fwhm_ps=0)
    class RNG:
        calls=0
        def poisson(self,mean):self.calls+=1;return 1
        def normal(self,mean,sigma,size):return np.zeros(size)
        def uniform(self,start,end,size):return np.zeros(size)
        def integers(self,start,end,size):return np.zeros(size,dtype=int)
    rng=RNG();captured={}
    monkeypatch.setattr(a_acquisition,'sample_pulse_offsets',lambda rng,shape,width,size:np.zeros(size))
    def route(config,times,pixels,trace_limit):
        captured['times']=np.asarray(times)
        return np.array([]),{'recorded':0},[]
    monkeypatch.setattr(a_acquisition,'route_events',route)
    a=Algorithms.load().model_copy(update={'readout_warmup_cycles':99})
    a_acquisition.event_histogram(cfg,photon_budget(cfg),rng,a,np.array([0,2048]))
    assert rng.calls==2*cfg.laser_shots
    assert len(captured['times'])==2*cfg.laser_shots
    assert np.all(captured['times']>=0)
    assert np.all(captured['times']<cfg.laser_shots*1e9/cfg.laser_prf_hz)


def test_start_fully_recovered_but_deadtime_continues_across_shots():
    cfg=SimulationConfig(range_m=20,laser_prf_hz=1000000,gate_start_ns=0,gate_width_ns=1000,
                         laser_shots=2,detector_operation='free_running',
                         spad_dead_time_ns=2000,tdc_dead_time_ns=2000)
    # A fictitious event before t=0 must not suppress the first measured event.
    times=[-5,5,1005,2000];pixels=[0,0,0,0]
    first=route_events(cfg,times,pixels)
    second=route_events(cfg,times,pixels)
    assert first[0].tolist()==second[0].tolist()==[5]
    assert first[1]['spad_dead_losses']==1  # next shot is still recovering
    assert first[1]['outside_acquisition_candidates']==2


def test_initial_tdc_is_ready_and_remains_busy_within_the_same_acquisition():
    cfg=SimulationConfig(range_m=20,laser_prf_hz=1000000,gate_start_ns=0,gate_width_ns=1000,
                         laser_shots=2,spad_dead_time_ns=0,tdc_dead_time_ns=2000)
    for _ in range(2):
        times,stats,_=route_events(cfg,[-5,5,1005],[0,0,0])
        assert times.tolist()==[5]
        assert stats['tdc_dead_losses']==1


def test_legacy_warmup_setting_has_no_effect_on_a_work_or_simulation(monkeypatch):
    cfg=SimulationConfig(monte_carlo_trials=2,readout_mean_trials=2,noise_mean_trials=2,laser_shots=2)
    original=Algorithms.load
    baseline=simulate(cfg,debug=True)
    monkeypatch.setattr(Algorithms,'load',classmethod(lambda cls:original().model_copy(update={'readout_warmup_cycles':99})))
    result=simulate(cfg,debug=True)
    assert result['histogram']==baseline['histogram']
    assert result['readout']==baseline['readout']
    assert result['readout']['initial_condition']=='fully_recovered'
    assert result['readout']['warmup_cycles']==0
    assert result['readout']['work_estimate']['cycles']==6*2

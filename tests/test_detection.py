import numpy as np
import pytest
from scipy.stats import binomtest
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import simulate
from spad_lidar.detection import binomial_interval, calibrate_threshold, evaluate_detection


@pytest.mark.parametrize('k,n',[(0,100),(100,100),(9,100),(1,1),(4,40)])
def test_exact_binomial_intervals(k,n):
    actual=binomial_interval(k,n,0.95)
    reference=binomtest(k,n).proportion_ci(confidence_level=0.95,method='exact')
    assert actual['ci_lower']==pytest.approx(reference.low)
    assert actual['ci_upper']==pytest.approx(reference.high)
    if k==0:assert actual['ci_upper']>0
    assert binomial_interval(0,0,0.95)['estimate'] is None


def test_calibration_order_and_insufficient_samples():
    threshold,rank=calibrate_threshold(np.arange(99),0.05)
    assert rank==95 and threshold==94
    with pytest.raises(ValueError,match='Insufficient'):
        calibrate_threshold([1,2],0.01)


def test_calibration_and_null_evaluation_use_separate_reproducible_streams():
    cfg=SimulationConfig()
    a=Algorithms.load()
    def sampler(rng):return np.array([rng.random()])
    def estimator(hist):return cfg.range_m,float(hist[0])
    result=evaluate_detection(cfg,a,np.array([0.0]),[np.array([1.0])],sampler,estimator,True)
    streams=np.random.SeedSequence(cfg.rng_seed).spawn(6)
    assert result['calibration']['scores']==np.random.default_rng(streams[4]).random(a.detector_calibration_trials).tolist()
    assert result['null_evaluation']['scores']==np.random.default_rng(streams[5]).random(a.detector_null_trials).tolist()
    assert result['observed']['distance_m'] is None
    assert result['pd']['estimate']==1
    tie=evaluate_detection(cfg,a,np.array([1.0]),[],lambda rng:np.array([1.0]),estimator,False)
    assert not tie['observed']['detected']
    assert tie['pd'] is None


@pytest.mark.parametrize('mode',['independent_multi','analytic_reference','shared_first','coincidence_fixed'])
def test_detector_does_not_change_observed_histogram_or_gt(mode):
    cfg=SimulationConfig(readout_mode=mode,monte_carlo_trials=3)
    enabled=simulate(cfg,debug=True)
    disabled=simulate(SimulationConfig(**{**cfg.model_dump(),'detection_enabled':False}),debug=True)
    assert enabled['histogram']==disabled['histogram']
    assert enabled['detection']['search_gate_ns']==[cfg.gate_start_ns,cfg.gate_start_ns+cfg.gate_width_ns]
    assert enabled['metrics']['raw_estimated_range_m']==disabled['metrics']['estimated_range_m']
    accepted=enabled['debug']['trial_estimates_m']
    assert accepted[0]==enabled['metrics']['estimated_range_m']


def test_no_events_are_rejected_and_no_trials_are_not_zero_pd():
    cfg=SimulationConfig(pulse_energy_nj=0,solar_enabled=False,other_light_enabled=False,dcr_cps_per_spad=0,monte_carlo_trials=0)
    result=simulate(cfg)
    assert result['metrics']['estimated_range_m'] is None
    assert result['metrics']['detection_status']=='not_detected'
    assert result['detection']['pfa']['estimate']==0
    assert result['detection']['pfa']['ci_upper']>0
    assert result['detection']['pd'] is None


def test_default_pure_noise_observation_is_not_reported_as_target():
    result=simulate(SimulationConfig(pulse_energy_nj=0))
    assert result['metrics']['raw_estimated_range_m'] is not None
    assert result['metrics']['estimated_range_m'] is None
    assert result['detection']['pd'] is None

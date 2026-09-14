import numpy as np
import pytest

from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import simulate, _preview_edges, signal_ground_truth, photon_budget, _time_axis


@pytest.mark.parametrize('mode', ['analytic_reference', 'independent_first', 'shared_multitdc', 'coincidence_fixed'])
def test_fine_histogram_rebins_to_coarse_expectation(mode):
    cfg=SimulationConfig(readout_mode=mode, range_m=1, pulse_energy_nj=0.001, gate_width_ns=10.05,
                         tdc_bin_ps=1000, laser_shots=10, monte_carlo_trials=0)
    result=simulate(cfg)
    h=result['histogram'];truth=h['ground_truth'];fine=truth['high_resolution'];factor=fine['subdivisions']
    assert np.asarray(fine['integrated_counts']).reshape(-1,factor).sum(axis=1) == pytest.approx(truth['counts'],abs=1e-10)
    assert np.asarray(fine['edges_ns'])[::factor] == pytest.approx(h['edges_ns'])
    assert fine['edges_ns'][-1] == pytest.approx(10.05)
    assert np.all(np.diff(fine['edges_ns'])>0)
    assert np.asarray(fine['counts_per_nominal_bin'])/fine['nominal_bin_width_ns'] == pytest.approx(fine['counts_per_ns'])
    assert sum(truth['counts']) == pytest.approx(truth['in_gate_total'])


def test_preview_resolution_does_not_change_acquisition_or_rng(monkeypatch):
    original=Algorithms.load()
    cfg=SimulationConfig(laser_shots=5,monte_carlo_trials=2)
    a=simulate(cfg,debug=True)
    monkeypatch.setattr(Algorithms,'load',classmethod(lambda cls:original.model_copy(update={'histogram_preview_subdivisions':4})))
    b=simulate(cfg,debug=True)
    for key in ('time_ns','edges_ns','expected_counts','expected_noise_counts','observed_counts'):
        assert a['histogram'][key] == b['histogram'][key]
    assert a['metrics'] == b['metrics']
    assert a['readout'] == b['readout']
    assert a['debug']['trial_estimates_m'] == b['debug']['trial_estimates_m']


def test_preview_resource_cap_is_explicit():
    a=Algorithms.load().model_copy(update={'histogram_preview_subdivisions':16,'max_histogram_preview_bins':20})
    edges,factor=_preview_edges(np.arange(6),a)
    assert factor == 4
    assert len(edges)-1 == 20
    with pytest.raises(ValueError,match='at least two'):
        _preview_edges(np.arange(12),a)


def test_ground_truth_is_independent_of_noise_readout_seed_and_repeats():
    cfg=SimulationConfig()
    algorithms=Algorithms.load()
    def truth(c,a):
        return signal_ground_truth(c,photon_budget(c),_time_axis(c)[0],a)
    baseline=truth(cfg,algorithms)
    varied=SimulationConfig(solar_illuminance_lux=0,other_light_enabled=False,dcr_cps_per_spad=0,
                            other_noise_cps_per_spad=100,readout_mode='shared_first',rng_seed=123,
                            monte_carlo_trials=3,spad_dead_time_ns=200,tdc_dead_time_ns=100)
    assert truth(varied,algorithms.model_copy(update={'readout_expected_trials':2})) == baseline
    assert baseline['in_gate_total'] == pytest.approx(cfg.laser_shots*photon_budget(cfg).signal_detected_per_pulse)
    assert sum(baseline['sensor_incident_counts']) == pytest.approx(cfg.laser_shots*photon_budget(cfg).signal_sensor_incident_photons_per_pulse)


@pytest.mark.parametrize('shape', ['gaussian','rectangular'])
@pytest.mark.parametrize('jitter', [0,173])
def test_continuous_density_integrates_to_ground_truth(shape,jitter):
    cfg=SimulationConfig(pulse_shape=shape,spad_jitter_fwhm_ps=jitter,other_jitter_fwhm_ps=0)
    truth=signal_ground_truth(cfg,photon_budget(cfg),_time_axis(cfg)[0],Algorithms.load())
    fine=truth['high_resolution']
    assert np.trapezoid(fine['counts_per_ns'],fine['time_ns']) == pytest.approx(truth['in_gate_total'],rel=5e-4)
    assert np.all(np.asarray(fine['counts_per_ns'])>=0)


def test_narrow_signal_peak_and_gate_truncation():
    cfg=SimulationConfig(range_m=1,pulse_fwhm_ps=1,spad_jitter_fwhm_ps=0,other_jitter_fwhm_ps=0,gate_width_ns=10.05)
    b=photon_budget(cfg)
    truth=signal_ground_truth(cfg,b,_time_axis(cfg)[0],Algorithms.load())
    assert np.trapezoid(truth['high_resolution']['counts_per_ns'],truth['high_resolution']['time_ns']) == pytest.approx(truth['in_gate_total'],rel=5e-4)
    from spad_lidar.constants import C
    gate_cfg=SimulationConfig(range_m=1,gate_start_ns=2/C*1e9,gate_width_ns=10.05)
    gate=signal_ground_truth(gate_cfg,photon_budget(gate_cfg),_time_axis(gate_cfg)[0],Algorithms.load())
    assert gate['in_gate_total'] == pytest.approx(gate['full_signal_total']/2)

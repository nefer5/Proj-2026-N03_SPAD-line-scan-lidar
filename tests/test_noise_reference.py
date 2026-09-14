import pytest
from fastapi.testclient import TestClient

from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import photon_budget


def test_sony_reference_defaults_and_api():
    defaults = TestClient(app).get('/api/defaults').json()
    assert defaults['dcr_cps_per_spad'] == 2007
    assert defaults['spad_jitter_fwhm_ps'] == 173
    assert defaults['spad_dead_time_ns'] == 6
    assert defaults['tdc_bin_ps'] == 1000
    assert defaults['readout_mode'] == 'independent_multi'
    assert defaults['laser_shots'] == 1
    assert defaults['tdc_max_hits_per_cycle'] == 1000
    assert defaults['tdc_dead_time_ns'] == 0


def test_dark_and_electronic_candidate_rates_do_not_use_pde_or_ff():
    settings = dict(H_binning=4, V_binning=4, gate_width_ns=2048,
                    dcr_cps_per_spad=2007, other_noise_cps_per_spad=100,
                    solar_enabled=False, other_light_enabled=False)
    first = photon_budget(SimulationConfig(**settings, fill_factor=1))
    second = photon_budget(SimulationConfig(**settings, fill_factor=0.1,
                                           pde_mode='constant', pde=0))
    assert first.dark_detected_per_gate == pytest.approx(0.065765376)
    assert second.dark_detected_per_gate == first.dark_detected_per_gate
    assert second.other_detected_per_gate == first.other_detected_per_gate
    assert first.other_detected_per_gate == pytest.approx(100*16*2048e-9)
    assert first.background_detected_per_gate == second.background_detected_per_gate == 0

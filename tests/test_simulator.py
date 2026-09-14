import numpy as np

from spad_lidar.models import FilterPoint, SimulationConfig
from spad_lidar.simulator import crosstalk_model, expected_histogram, photon_budget, simulate


def test_lambertian_signal_follows_inverse_square():
    cfg = SimulationConfig(range_m=20.0, gate_width_ns=1000.0, monte_carlo_trials=0)
    near = photon_budget(cfg, 20.0).signal_detected_per_pulse
    far = photon_budget(cfg, 40.0).signal_detected_per_pulse
    assert np.isclose(near / far, 4.0)


def test_filter_curve_controls_background_and_laser_transmission():
    cfg = SimulationConfig(
        wavelength_nm=940,
        filter_interpolation="linear",
        filter_curve=[
            FilterPoint(wavelength_nm=930, transmission=0),
            FilterPoint(wavelength_nm=940, transmission=0.8),
            FilterPoint(wavelength_nm=950, transmission=0),
        ]
    )
    budget = photon_budget(cfg)
    assert np.isclose(budget.filter_transmission_at_laser, 0.8)
    assert np.isclose(budget.filter_enbw_nm, 8.0)


def test_expected_histogram_peak_is_at_tof():
    cfg = SimulationConfig(range_m=30.0, gate_width_ns=400.0, tdc_bin_ps=100, pulse_fwhm_ps=700, pulse_energy_nj=0.5, monte_carlo_trials=0)
    t, hist, noise, _ = expected_histogram(cfg)
    peak_t = t[int(np.argmax(hist - noise))]
    expected_t = 2.0 * cfg.range_m / 299_792_458.0 * 1e9
    assert abs(peak_t - expected_t) < 0.2


def test_crosstalk_matrix_has_zero_direct_diagonal_and_positive_neighbors():
    cfg = SimulationConfig(line_channels=8, gate_width_ns=1000.0, monte_carlo_trials=0)
    direct, total = crosstalk_model(cfg)
    assert np.allclose(np.diag(direct), 0.0)
    assert direct[3, 4] > direct[2, 4] > 0
    assert np.all(total >= 0)


def test_simulation_returns_finite_metrics():
    cfg = SimulationConfig(
        range_m=20.0,
        gate_width_ns=300.0,
        pulse_energy_nj=20.0,
        pde_mode="constant", pde=0.15, fill_factor=0.2,
        laser_shots=100,
        monte_carlo_trials=5,
    )
    result = simulate(cfg)
    assert np.isfinite(result["metrics"]["estimated_range_m"])
    assert len(result["histogram"]["time_ns"]) == len(result["histogram"]["observed_counts"])

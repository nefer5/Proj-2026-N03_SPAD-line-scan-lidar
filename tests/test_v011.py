import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from spad_lidar import configuration
from spad_lidar.api import app
from spad_lidar.constants import C
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import (
    aperture_area, photon_budget, derived_quantities, _signal_shape,
    _time_axis, _first_photon_probabilities, crosstalk_model, simulate,
)

client = TestClient(app)


def test_yaml_is_complete_and_all_parameters_documented():
    defaults = configuration.default_values()
    assert set(defaults) == set(SimulationConfig.model_fields)
    assert set(defaults) == set(configuration.read_yaml("parameter-help.yaml"))
    assert all(field.is_required() for field in SimulationConfig.model_fields.values())
    assert SimulationConfig().model_dump() == defaults


def test_defaults_are_reread_without_server_restart(tmp_path, monkeypatch):
    values = configuration.read_yaml("defaults.yaml")
    values["simulation"]["laser_shots"] = 123
    (tmp_path / "readout-modes.yaml").write_text(yaml.safe_dump(configuration.read_yaml("readout-modes.yaml")), encoding="utf-8")
    (tmp_path / "defaults.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    (tmp_path / "algorithms.yaml").write_text(
        yaml.safe_dump(configuration.read_yaml("algorithms.yaml")), encoding="utf-8")
    monkeypatch.setattr(configuration, "CONFIG_DIR", tmp_path)
    assert client.get("/api/defaults").json()["laser_shots"] == 123
    values["simulation"]["laser_shots"] = 321
    (tmp_path / "defaults.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    assert client.get("/api/defaults").json()["laser_shots"] == 321
    assert SimulationConfig(laser_shots=456).laser_shots == 456


@pytest.mark.parametrize("shape,area", [("circle", np.pi*100), ("ellipse",np.pi*50), ("rectangle",200)])
def test_aperture_shape_changes_both_signal_and_background(shape, area):
    cfg = SimulationConfig(rx_aperture_shape=shape, rx_aperture_mm=20,
                           rx_aperture_width_mm=20, rx_aperture_height_mm=10)
    assert aperture_area(cfg)*1e6 == pytest.approx(area)
    reference = photon_budget(SimulationConfig(rx_aperture_shape="rectangle",
                                               rx_aperture_width_mm=20, rx_aperture_height_mm=10))
    budget = photon_budget(cfg)
    assert budget.signal_detected_per_pulse/reference.signal_detected_per_pulse == pytest.approx(area/200)
    assert budget.background_detected_per_gate/reference.background_detected_per_gate == pytest.approx(area/200)
    assert budget.dark_detected_per_gate == reference.dark_detected_per_gate


@pytest.mark.parametrize("shape", ["gaussian", "rectangular"])
def test_pulse_power_integral_and_prf(shape):
    cfg = SimulationConfig(pulse_shape=shape)
    d = derived_quantities(cfg)
    width = cfg.pulse_fwhm_ps*1e-12
    factor = np.sqrt(np.pi/(4*np.log(2))) if shape == "gaussian" else 1
    assert d["peak_power_w"]*width*factor == pytest.approx(cfg.pulse_energy_nj*1e-9)
    assert d["average_power_w"] == pytest.approx(cfg.pulse_energy_nj*1e-9*cfg.laser_prf_hz)
    assert d["acquisition_time_ms"] == pytest.approx(cfg.laser_shots/cfg.laser_prf_hz*1000)
    higher = derived_quantities(SimulationConfig(pulse_shape=shape, laser_prf_hz=1.1e6))
    assert higher["peak_power_w"] == d["peak_power_w"]
    assert higher["average_power_w"] == pytest.approx(d["average_power_w"]*1.1)


@pytest.mark.parametrize("shape", ["gaussian","rectangular"])
def test_gate_truncation_does_not_renormalize_signal(shape):
    r = 30
    cfg = SimulationConfig(range_m=r, pulse_shape=shape, gate_start_ns=2*r/C*1e9,
                           gate_width_ns=100, spad_jitter_fwhm_ps=0, other_jitter_fwhm_ps=0)
    edges, _ = _time_axis(cfg)
    weights = _signal_shape(cfg, edges)
    assert weights.sum() == pytest.approx(0.5, abs=1e-10)


def test_rectangular_shape_is_not_gaussian_and_partial_bin():
    cfg = SimulationConfig(pulse_shape="rectangular", spad_jitter_fwhm_ps=0, other_jitter_fwhm_ps=0)
    center = 2*cfg.range_m/C*1e9
    width_ns = cfg.pulse_fwhm_ps*1e-3
    edges = center + np.linspace(-width_ns/2,width_ns/2,8)
    assert _signal_shape(cfg,edges) == pytest.approx(np.full(7,1/7))
    partial = SimulationConfig(range_m=1, gate_width_ns=10.05, tdc_bin_ps=100)
    edges, _ = _time_axis(partial)
    assert edges[-1] == 10.05
    assert np.diff(edges)[-1] == pytest.approx(0.05)


def test_first_photon_probabilities_conserve_probability():
    mu = np.array([0.1,2.0,0.4])
    assert _first_photon_probabilities(mu).sum()+np.exp(-mu.sum()) == pytest.approx(1)
    assert _first_photon_probabilities(mu)[1] == pytest.approx(np.exp(-0.1)*(1-np.exp(-2)))


def test_debug_and_evaluation_are_identical_for_same_configuration():
    cfg = SimulationConfig(monte_carlo_trials=3)
    basic, debug = simulate(cfg), simulate(cfg,debug=True)
    for key in ("histogram","metrics","budget","configuration","derived","range_sweep","crosstalk"):
        assert basic[key] == debug[key]
    assert len(debug["debug"]["trial_estimates_m"]) == 3
    assert debug["debug"]["steps"][3]["values"]["probability_sum_with_no_event"] == pytest.approx(1)
    json.dumps(debug, allow_nan=False)


def test_zero_photons_and_zero_trials_are_json_safe():
    cfg = SimulationConfig(pulse_energy_nj=0,background_spectral_radiance=0,solar_enabled=False,other_light_enabled=False,
                           dcr_cps_per_spad=0,monte_carlo_trials=0)
    result = client.post("/api/simulate?debug=true",json=cfg.model_dump())
    assert result.status_code == 200
    data = result.json()
    assert data["metrics"]["estimated_range_m"] is None
    assert data["metrics"]["precision_cm_1sigma"] is None
    assert data["metrics"]["success_rate"] is None


def test_no_detection_counts_as_failure_in_repeats():
    data = simulate(SimulationConfig(pulse_energy_nj=0,background_spectral_radiance=0,solar_enabled=False,other_light_enabled=False,
                                     dcr_cps_per_spad=0,monte_carlo_trials=4), debug=True)
    assert data["metrics"]["success_rate"] == 0
    assert data["metrics"]["trials_completed"] == 4
    assert data["metrics"]["valid_trials"] == 0


def test_yaml_export_import_round_trip_and_unknown_keys():
    original = SimulationConfig(pulse_shape="rectangular",rx_aperture_shape="ellipse")
    export = client.post("/api/config/export",json=original.model_dump())
    assert export.status_code == 200
    imported = client.post("/api/config/import",content=export.text,headers={"Content-Type":"text/plain"})
    assert imported.status_code == 200
    assert imported.json() == original.model_dump()
    for text in ("laser_shots: 1\nlaser_shots: 2", "laser_shoots: 10", "pde: .nan", "range_m: -1"):
        response=client.post("/api/config/import",content=text,headers={"Content-Type":"text/plain"})
        assert response.status_code == 422


def test_invalid_shapes_prf_and_filter_rejected():
    for overrides in ({"rx_aperture_shape":"triangle"},{"laser_prf_hz":1e8},
                      {"rx_aperture_width_mm":0},{"filter_curve":[{"wavelength_nm":940,"transmission":1}]}):
        with pytest.raises(ValidationError):
            SimulationConfig(**overrides)


def test_broken_yaml_returns_actionable_error(tmp_path, monkeypatch):
    (tmp_path / "defaults.yaml").write_text("invalid: [", encoding="utf-8")
    monkeypatch.setattr(configuration, "CONFIG_DIR", tmp_path)
    response = client.get("/api/defaults")
    assert response.status_code == 503
    assert "config/defaults.yaml" in response.json()["detail"]


def test_unstable_crosstalk_is_rejected_not_silently_scaled():
    with pytest.raises(ValueError, match="spectral radius"):
        crosstalk_model(SimulationConfig(nearest_neighbor_crosstalk=0.9))


def test_docs_use_vscode_math_delimiters():
    docs = Path(__file__).resolve().parents[1]/"docs"
    for path in docs.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "\\[" not in text and "\\]" not in text
        assert "\\(" not in text and "\\)" not in text
        assert not any(line.strip()=="$" for line in text.splitlines())
        assert sum(line.strip()=="$$" for line in text.splitlines()) % 2 == 0

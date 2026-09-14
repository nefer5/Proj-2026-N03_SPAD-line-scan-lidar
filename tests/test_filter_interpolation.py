import numpy as np
import pytest
from scipy.integrate import quad
from fastapi.testclient import TestClient

from spad_lidar.api import app
from spad_lidar.models import SimulationConfig, FilterPoint
from spad_lidar.configuration import Algorithms
from spad_lidar.filters import FilterResponse
from spad_lidar.simulator import filter_profile, photon_budget

POINTS = [FilterPoint(wavelength_nm=930, transmission=0),
          FilterPoint(wavelength_nm=940, transmission=0.8),
          FilterPoint(wavelength_nm=950, transmission=0)]


def test_pchip_values_and_integral_have_analytic_reference():
    # These three knots produce the parabola .8*(1-((lambda-940)/10)^2).
    cfg = SimulationConfig(wavelength_nm=945,filter_curve=POINTS,filter_interpolation="pchip")
    response = FilterResponse(cfg)
    assert response.evaluate(945) == pytest.approx(0.6)
    assert response.integral_nm() == pytest.approx(0.8*40/3)
    assert photon_budget(cfg).filter_transmission_at_laser == pytest.approx(0.6)
    assert photon_budget(cfg).filter_enbw_nm == pytest.approx(0.8*40/3)


@pytest.mark.parametrize("method",["pchip","linear"])
def test_interpolation_passes_through_every_knot_and_is_bounded(method):
    cfg=SimulationConfig(filter_curve=POINTS,filter_interpolation=method)
    response=FilterResponse(cfg)
    assert response.evaluate([930,940,950]) == pytest.approx([0,0.8,0])
    dense=response.evaluate(np.linspace(930,950,2001))
    assert dense.min()>=-1e-14
    assert dense.max()<=0.8+1e-14
    assert response.evaluate([929,951]) == pytest.approx([0,0])
    assert response.integral_nm() == pytest.approx(quad(response.evaluate,930,950,points=[940])[0])


def test_plot_keeps_original_scatter_and_dense_interpolated_curve_separate():
    cfg=SimulationConfig(filter_curve=POINTS,filter_interpolation="pchip")
    profile=filter_profile(cfg)
    assert profile["original_wavelength_nm"]==[930,940,950]
    assert profile["original_transmission"]==[0,0.8,0]
    assert len(profile["wavelength_nm"])>len(POINTS)
    assert profile["polynomial_coefficients"] is not None
    response=FilterResponse(cfg)
    # Endpoint zeros are explicitly duplicated for a discontinuous out-of-band cutoff.
    for x,y in zip(profile["wavelength_nm"][2:-2],profile["transmission"][2:-2]):
        assert y == pytest.approx(response.evaluate(x))


def test_plot_resolution_does_not_change_budget_integral():
    cfg=SimulationConfig(filter_curve=POINTS,filter_interpolation="pchip")
    algorithms=Algorithms.load()
    coarse=filter_profile(cfg,algorithms.model_copy(update={"filter_plot_samples":5}))
    dense=filter_profile(cfg,algorithms.model_copy(update={"filter_plot_samples":2001}))
    assert coarse["weighted_bandwidth_nm"]==dense["weighted_bandwidth_nm"]
    assert coarse["laser_transmission"]==dense["laser_transmission"]


def test_two_points_flat_and_rectangular_filters():
    for method in ("pchip","linear"):
        cfg=SimulationConfig(filter_interpolation=method,
                             filter_curve=[FilterPoint(wavelength_nm=900,transmission=0.5),
                                           FilterPoint(wavelength_nm=1000,transmission=0.5)])
        assert FilterResponse(cfg).integral_nm()==pytest.approx(50)
        assert FilterResponse(cfg).evaluate(940)==pytest.approx(0.5)
    rectangle=filter_profile(SimulationConfig(filter_curve=None,filter_peak_transmission=0.8))
    assert rectangle["original_wavelength_nm"]==[]
    assert rectangle["interpolation"]=="rectangular"
    assert rectangle["weighted_bandwidth_nm"]==pytest.approx(8)


def test_selecting_interpolation_changes_physical_signal_and_background():
    linear=photon_budget(SimulationConfig(wavelength_nm=945,filter_curve=POINTS,filter_interpolation="linear",solar_enabled=False,other_light_mode="constant",pde_mode="constant"))
    pchip=photon_budget(SimulationConfig(wavelength_nm=945,filter_curve=POINTS,filter_interpolation="pchip",solar_enabled=False,other_light_mode="constant",pde_mode="constant"))
    assert pchip.signal_detected_per_pulse/linear.signal_detected_per_pulse==pytest.approx(1.5)
    assert pchip.background_detected_per_gate/linear.background_detected_per_gate==pytest.approx(4/3)
    assert pchip.dark_detected_per_gate==linear.dark_detected_per_gate


def test_yaml_roundtrip_preserves_sparse_points_and_method_and_rejects_bad_knots():
    client=TestClient(app)
    cfg=SimulationConfig(filter_curve=POINTS,filter_interpolation="pchip")
    exported=client.post("/api/config/export",json=cfg.model_dump())
    imported=client.post("/api/config/import",content=exported.text,headers={"Content-Type":"text/plain"})
    assert imported.json()==cfg.model_dump()
    for points in ([{"wavelength_nm":940,"transmission":0.5}]*2,
                   [{"wavelength_nm":940,"transmission":1.1},{"wavelength_nm":950,"transmission":0}],
                   [{"wavelength_nm":950,"transmission":0},{"wavelength_nm":940,"transmission":0.5}]):
        assert client.post("/api/derived",json={"filter_curve":points}).status_code==422

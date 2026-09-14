from hashlib import sha256
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from spad_lidar import api
from spad_lidar.models import SimulationConfig, FilterPoint
from spad_lidar.simulator import derived_quantities, photon_budget

client = TestClient(api.app)


def test_html_uses_content_hash_for_js_and_css_and_all_routes_are_uncached():
    for route in ("/", "/debug"):
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        for name in ("app.js", "styles.css"):
            digest = sha256((api.WEB/name).read_bytes()).hexdigest()
            assert f"/static/{name}?v={digest}" in response.text
            asset = client.get(f"/static/{name}?v={digest}")
            assert asset.status_code == 200
            assert asset.headers["cache-control"] == "no-store"


def test_file_change_changes_asset_url_without_manual_version_bump(tmp_path, monkeypatch):
    for name in ("index.html", "app.js", "styles.css", "vendor/katex/katex.min.js", "vendor/katex/katex.min.css"):
        (tmp_path/name).parent.mkdir(parents=True,exist_ok=True)
        (tmp_path/name).write_bytes((api.WEB/name).read_bytes())
    monkeypatch.setattr(api, "WEB", tmp_path)
    first = client.get("/").text
    with (tmp_path/"app.js").open("a",encoding="utf-8") as file:
        file.write("\n// Changed in temporary QA checkout\n")
    second = client.get("/").text
    extract = lambda text: re.search(r'/static/app.js\?v=([a-f0-9]+)',text).group(1)
    assert extract(first) != extract(second)


def test_rectangular_filter_chart_area_matches_budget():
    cfg = SimulationConfig(filter_bandwidth_nm=10,filter_peak_transmission=0.8)
    curve = derived_quantities(cfg)["filter"]
    area = np.trapezoid(curve["transmission"],curve["wavelength_nm"])
    assert area == pytest.approx(8)
    assert curve["weighted_bandwidth_nm"] == pytest.approx(area)
    assert curve["laser_transmission"] == photon_budget(cfg).filter_transmission_at_laser


def test_imported_curve_display_matches_interpolation_and_out_of_band():
    points = [FilterPoint(wavelength_nm=930,transmission=0),
              FilterPoint(wavelength_nm=940,transmission=0.8),
              FilterPoint(wavelength_nm=950,transmission=0)]
    cfg=SimulationConfig(wavelength_nm=945,filter_curve=points,filter_interpolation="linear")
    curve=derived_quantities(cfg)["filter"]
    assert curve["source"] == "csv_curve"
    assert curve["laser_transmission"] == pytest.approx(0.4)
    assert curve["weighted_bandwidth_nm"] == pytest.approx(8)
    assert np.trapezoid(curve["transmission"],curve["wavelength_nm"]) == pytest.approx(8)
    outside=SimulationConfig(wavelength_nm=960,filter_curve=points)
    chart=derived_quantities(outside)["filter"]
    assert chart["laser_transmission"] == 0
    assert photon_budget(outside).signal_detected_per_pulse == 0
    assert chart["wavelength_nm"][-1] > 960


def test_valid_selects_reach_backend_while_old_nulls_are_rejected():
    assert client.post("/api/simulate",json={"pulse_shape":"rectangular","rx_aperture_shape":"ellipse","monte_carlo_trials":0}).status_code==200
    response=client.post("/api/simulate",json={"pulse_shape":None,"rx_aperture_shape":None})
    assert response.status_code==422
    assert {error["loc"][-1] for error in response.json()["detail"]}=={"pulse_shape","rx_aperture_shape"}


def test_legacy_diagnostic_does_not_block_single_channel_a():
    base=client.post("/api/simulate",json={"monte_carlo_trials":0}).json()
    response=client.post("/api/simulate",json={"monte_carlo_trials":0,"nearest_neighbor_crosstalk":0.9})
    assert response.status_code==200
    assert response.json()["crosstalk"]["status"]=="invalid"
    assert response.json()["histogram"]==base["histogram"]

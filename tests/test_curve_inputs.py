import numpy as np
import pytest
from scipy.integrate import quad
from fastapi.testclient import TestClient
from spad_lidar.models import SimulationConfig
from spad_lidar.curves import Curve
from spad_lidar.spectra import spectral_components
from spad_lidar.simulator import photon_budget
from spad_lidar.api import app

client=TestClient(app)


def cfg_curve(kind,**basic):
    if kind=='filter':
        basic={"center_nm":940,"min_nm":900,"max_nm":980,"width_nm":10,"flat_width_nm":8,"edge_width_nm":2,"amplitude":0.8,**basic}
    return SimulationConfig(spectral_inputs={kind:{"mode":"basic","basic":basic}})


@pytest.mark.parametrize("shape,area",[
    ("constant",0.8*80),("rectangle",0.8*10),
    ("gaussian",0.8*10*np.sqrt(np.pi/(4*np.log(2)))),
    ("cosine_flat",0.8*(8+2)),
])
def test_basic_shapes_area_and_finite_support(shape,area):
    cfg=cfg_curve("filter",shape=shape)
    curve=Curve(cfg.spectral_inputs.filter)
    assert curve.integral_nm()==pytest.approx(area,rel=1e-10)
    assert curve.evaluate([899,981]).tolist()==[0,0]
    assert curve.integral_nm()==pytest.approx(quad(curve.evaluate,900,980,points=curve.knots(),limit=200)[0])


def test_gaussian_fwhm_and_cosine_transition_definition():
    gaussian=Curve(cfg_curve("filter",shape="gaussian").spectral_inputs.filter)
    assert gaussian.evaluate([935,940,945])==pytest.approx([0.4,0.8,0.4])
    cosine=Curve(cfg_curve("filter",shape="cosine_flat").spectral_inputs.filter)
    assert cosine.evaluate([934,935,936,940,944,945,946])==pytest.approx([0,0.4,0.8,0.8,0.8,0.4,0])


@pytest.mark.parametrize("kind",["filter","other","pde","solar"])
@pytest.mark.parametrize("shape",["constant","rectangle","gaussian","cosine_flat"])
def test_all_groups_accept_basic_families(kind,shape):
    cfg=cfg_curve(kind,shape=shape)
    assert Curve(getattr(cfg.spectral_inputs,kind)).evaluate(np.array([500,940])).shape==(2,)


def test_csv_and_manual_banks_are_separate_and_roundtrip():
    csv=[{"wavelength_nm":930,"value":0.2},{"wavelength_nm":950,"value":0.2}]
    manual=[{"wavelength_nm":930,"value":0.7},{"wavelength_nm":950,"value":0.7}]
    cfg=SimulationConfig(spectral_inputs={"filter":{"mode":"csv","csv_name":"curve.csv","csv_points":csv,"manual_points":manual}})
    assert Curve(cfg.spectral_inputs.filter).evaluate(940)==pytest.approx(0.2)
    data=cfg.model_dump();data["spectral_inputs"]["filter"]["mode"]="manual"
    switched=SimulationConfig.model_validate(data)
    assert Curve(switched.spectral_inputs.filter).evaluate(940)==pytest.approx(0.7)
    yaml=client.post("/api/config/export",json=switched.model_dump()).text
    imported=client.post("/api/config/import",content=yaml,headers={"Content-Type":"text/plain"}).json()
    assert imported==switched.model_dump()


def test_active_empty_csv_invalid_probabilities_and_unknown_fields_rejected():
    assert client.post("/api/derived",json={"spectral_inputs":{"pde":{"mode":"csv"}}}).status_code==422
    for override in ({"amplitude":1.1},{"min_nm":1000,"max_nm":900},{"shape":"triangle"}):
        assert client.post("/api/derived",json={"spectral_inputs":{"pde":{"mode":"basic","basic":override}}}).status_code==422
    assert client.post("/api/derived",json={"spectral_inputs":{"filter":{"mode":"standard"}}}).status_code==422


def test_joint_gaussian_cosine_integral_matches_independent_quadrature():
    cfg=SimulationConfig(solar_enabled=False,spectral_inputs={
        "filter":{"mode":"basic","basic":{"shape":"gaussian","width_nm":1}},
        "pde":{"mode":"basic","basic":{"shape":"cosine_flat","center_nm":940,"flat_width_nm":2,"edge_width_nm":3}},
        "other":{"mode":"basic","basic":{"shape":"constant"}},
    })
    components=spectral_components(cfg)
    f=Curve(cfg.spectral_inputs.filter);p=Curve(cfg.spectral_inputs.pde);o=Curve(cfg.spectral_inputs.other)
    from spad_lidar.constants import H,C
    value=quad(lambda x:f(x)*p(x)*o(x)*x*1e-9/(H*C),930,950,epsabs=0,epsrel=1e-10,points=[934,937,939,940,941,943,946])[0]
    assert components["other_detectable_photons_s_m2_sr"]==pytest.approx(value,rel=1e-9)


def test_solar_custom_shape_normalizes_lux_and_rejects_infrared_only():
    cfg=cfg_curve("solar",shape="gaussian")
    a=spectral_components(cfg)
    altered=cfg.model_dump();altered["spectral_inputs"]["solar"]["basic"]["amplitude"]=10
    b=spectral_components(SimulationConfig.model_validate(altered))
    assert a["solar_lux"]==50000
    assert a["solar_detectable_photons_s_m2_sr"]==pytest.approx(b["solar_detectable_photons_s_m2_sr"])
    bad=cfg_curve("solar",shape="constant",min_nm=900,max_nm=1000)
    with pytest.raises(ValueError,match="visible"):
        spectral_components(bad)
    assert client.post('/api/derived',json=bad.model_dump()).status_code==422


def test_old_config_import_migrates_and_exports_only_new_schema():
    old={"filter_curve":[{"wavelength_nm":930,"transmission":0},{"wavelength_nm":950,"transmission":0.8}],
         "pde_mode":"constant","pde":0.25,"other_light_mode":"constant","background_spectral_radiance":0.03}
    cfg=SimulationConfig.model_validate(old)
    assert cfg.spectral_inputs.filter.mode=="manual"
    assert cfg.spectral_inputs.pde.basic.amplitude==0.25
    assert "pde_mode" not in cfg.model_dump()
    assert client.post("/api/simulate",json={**old,"monte_carlo_trials":0,"laser_shots":10}).status_code==200

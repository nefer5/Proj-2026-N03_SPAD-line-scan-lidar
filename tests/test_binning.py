import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import photon_budget,simulate,derived_quantities
from spad_lidar.configuration import Algorithms


def test_product_is_derived_and_not_serialized_as_input():
    cfg=SimulationConfig(H_binning=4,V_binning=8)
    assert cfg.spads_per_channel==32
    assert 'spads_per_channel' not in cfg.model_dump()
    assert derived_quantities(cfg)['binning']=={'H_binning':4,'V_binning':8,'spads_per_channel':32}


@pytest.mark.parametrize('changes',[{'H_binning':0},{'V_binning':-1},{'H_binning':2.5},{'V_binning':True},{'H_binning':'4'}])
def test_axes_must_be_positive_integers(changes):
    with pytest.raises(ValidationError):SimulationConfig(**changes)


def test_product_limit_and_coincidence_threshold_use_total():
    with pytest.raises(ValidationError,match='resource limit'):
        SimulationConfig(H_binning=Algorithms.load().max_spads_per_channel,V_binning=2)
    with pytest.raises(ValidationError,match='Coincidence'):
        SimulationConfig(H_binning=2,V_binning=2,readout_mode='coincidence_fixed',coincidence_threshold=5)


def test_legacy_count_becomes_one_row_without_guessing_shape():
    cfg=SimulationConfig(spads_per_channel=16)
    assert (cfg.H_binning,cfg.V_binning)==(16,1)
    for data in ({'spads_per_channel':16,'H_binning':4},{'spads_per_channel':16,'H_binning':4,'V_binning':4}):
        with pytest.raises(ValidationError,match='mix'):SimulationConfig(**data)


def test_same_total_produces_identical_a_model_histogram():
    a=simulate(SimulationConfig(H_binning=4,V_binning=4,monte_carlo_trials=0,laser_shots=10))
    b=simulate(SimulationConfig(H_binning=8,V_binning=2,monte_carlo_trials=0,laser_shots=10))
    assert a['histogram']==b['histogram']
    assert a['budget']==b['budget']


def test_more_spads_scales_dcr_not_total_optical_budget_or_ifov():
    a=photon_budget(SimulationConfig(H_binning=4,V_binning=4))
    b=photon_budget(SimulationConfig(H_binning=4,V_binning=8))
    assert b.dark_detected_per_gate==pytest.approx(a.dark_detected_per_gate*2)
    assert b.signal_detected_per_pulse==a.signal_detected_per_pulse
    assert b.background_detected_per_gate==a.background_detected_per_gate
    assert b.channel_solid_angle_sr==a.channel_solid_angle_sr


def test_yaml_roundtrip_preserves_both_axes_and_legacy_import_works():
    client=TestClient(app)
    cfg=SimulationConfig(H_binning=3,V_binning=7)
    exported=client.post('/api/config/export',json=cfg.model_dump())
    imported=client.post('/api/config/import',content=exported.text,headers={'Content-Type':'text/plain'})
    assert imported.json()==cfg.model_dump()
    legacy=client.post('/api/config/import',content='spads_per_channel: 21',headers={'Content-Type':'text/plain'})
    assert legacy.json()['H_binning']==21 and legacy.json()['V_binning']==1

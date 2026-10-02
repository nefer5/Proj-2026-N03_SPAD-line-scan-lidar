import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.system_budget import calculate_budget


def calc(overrides):
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',overrides,a)
    return c,calculate_budget(c,a)


def test_line_power_angle_and_energy_conservation():
    c,r=calc({});m=r['metrics'];n=c.system.spad.channels_v
    assert c.system.spad.channels_h==1 and c.system.tx.tx_model=='uniform'
    assert m['channel_power_w']*n==pytest.approx(m['pulse_average_power_w'])
    assert m['channel_energy_nj']*n==pytest.approx(m['single_pulse_energy_nj'])
    assert m['tx_channel_v_deg']*n==pytest.approx(c.geometry.vfov_deg)
    assert sum(row['signal_candidates_per_column'] for row in r['vertical_budget']['rows'])==pytest.approx(m['signal_candidates_per_column'])
    assert sum(row['background_candidates_per_column'] for row in r['vertical_budget']['rows'])==pytest.approx(m['background_candidates_per_column'])


def test_rx_is_per_channel_and_independent():
    c,r=calc({'rx_channel':{'v_width_deg':.1,'h_width_mrad':3}})
    n=c.system.spad.channels_v;dv=c.geometry.vfov_deg/n
    assert r['metrics']['rx_channel_v_deg']==pytest.approx(.1)
    assert c.system.rx.rx_angle_v_max_mrad-c.system.rx.rx_angle_v_min_mrad==pytest.approx((n-1)*dv*3.141592653589793/180*1000+.1*3.141592653589793/180*1000)
    _,changed=calc({'rx_channel':{'v_width_deg':.1,'h_width_mrad':3},'geometry':{'tx_h_width_mrad':1}})
    assert changed['metrics']['background_candidates_per_column']==r['metrics']['background_candidates_per_column']


def test_hardware_coordinate_conversion_and_render_channel_data():
    c,r=calc({});s=r['schematic']
    assert 'negative_X_Z' in s['coordinate_convention']
    assert s['tx_corners'][2][0]<0 and s['tx_corners'][2][1]>0
    assert len(s['channel_regions'])==c.system.spad.channels_v
    assert len(s['detector_cells'])==c.system.spad.channels_v*c.system.spad.spads_per_channel


@pytest.mark.parametrize('bad',[{'system':{'spad':{'channels_h':2}}},{'system':{'tx':{'tx_model':'gaussian'}}},{'rx_channel':{'h_width_mrad':0}},{'rx_channel':{'v_width_deg':float('nan')}},{'geometry':{'vfov_deg':None}}])
def test_conflicting_models_are_rejected(bad):
    with pytest.raises(ValueError):SimulationConfig.for_experiment('budget',bad)


def test_v3_migration_is_explicit_and_preserves_original():
    from copy import deepcopy
    from spad_lidar.legacy_config import migrate_budget_v3
    original=SimulationConfig.for_experiment('budget',{}).model_dump()
    original.pop('rx_channel')
    original['system']['spad']['channels_h']=2
    original['system']['tx']['tx_model']='gaussian'
    before=deepcopy(original)
    changed=migrate_budget_v3(original)
    assert original==before
    assert changed['system']['spad']['channels_h']==1
    assert changed['system']['tx']['tx_model']=='uniform'
    assert changed['system']['tx']['pulse_average_power_w']==before['system']['tx']['pulse_average_power_w']
    assert changed['rx_channel']['v_width_deg']==pytest.approx(before['geometry']['vfov_deg']/before['system']['spad']['channels_v'])


def test_system_vfov_has_own_default_and_channel_units():
    import math
    from spad_lidar.configuration import read_yaml
    c,r=calc({'geometry':{'vfov_deg':12},'system':{'spad':{'channels_v':4}}})
    assert r['metrics']['tx_channel_v_deg']==pytest.approx(3)
    assert r['metrics']['tx_channel_v_mrad']==pytest.approx(math.radians(3)*1000)
    default=SimulationConfig.for_experiment('budget',{})
    assert default.geometry.vfov_deg==read_yaml('defaults.yaml')['experiments']['budget_geometry']['vfov_deg']
    changed=SimulationConfig.for_experiment('budget',{'system':{'tx':{'angle_v_min_mrad':-1,'angle_v_max_mrad':1}}})
    assert changed.geometry.vfov_deg==default.geometry.vfov_deg


def test_whole_field_layout_and_rx_difference_are_explicit():
    import math
    c,r=calc({'system':{'spad':{'channels_v':5}},'rx_channel':{'v_width_deg':.02}})
    scene=r['schematic'];view=scene['views']
    assert scene['source_position'][0]==scene['origin'][0]
    assert scene['source_position'][2]<scene['origin'][2]
    assert scene['pupil_position'][2]==scene['detector_position'][2]==scene['origin'][2]
    assert len(view['surface'])>0 and len(view['column_regions'])==c.targets.slot_count
    assert view['channels'][0]['detector_group']==4
    assert not view['rx_v_follows_tx'] and not view['same_v_width']
    assert view['rx_v_envelope_mrad']==pytest.approx(4*r['metrics']['tx_channel_v_mrad']+r['metrics']['rx_channel_v_mrad'])
    assert r['metrics']['horizontal_angle_step_mrad']==pytest.approx(math.radians(c.targets.hfov_deg/c.targets.slot_count)*1000)
    _,follow=calc({'system':{'spad':{'channels_v':5}},'rx_channel':{'v_width_deg':None}})
    assert follow['schematic']['views']['same_v_width']
    assert follow['schematic']['views']['rx_v_envelope_mrad']==pytest.approx(follow['schematic']['views']['tx_v_envelope_mrad'])

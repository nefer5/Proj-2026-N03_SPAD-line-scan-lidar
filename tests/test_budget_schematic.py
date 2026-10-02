import math
import json
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.experiments.spatial import project_illumination
from spad_lidar.reporting.budget_schematic import budget_schematic


@pytest.fixture(scope='module')
def data():
    # Exercise physical-cell rendering inside the optical and display limits,
    # independently of the user's full-array budget profile.
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',{
        'geometry':{'vfov_deg':1},
        'system':{'spad':{'channels_v':16,'H_binning':2,'V_binning':2}}})
    _,_,o=project_illumination(c.system,a,lambda *_:None,lambda:False)
    return c,a,o,budget_schematic(c,o,a)


def test_geometry_projects_configuration_with_disclosed_scale(data):
    c,a,o,s=data
    r=c.system.scene.range_m;scale=s['scale']['transverse_units_per_m']
    corner=s['tx_corners'][2]
    assert corner[0]/scale==pytest.approx(-r*math.tan(c.system.tx.angle_h_max_mrad*1e-3))
    assert corner[1]/scale==pytest.approx(r*math.tan(c.system.tx.angle_v_max_mrad*1e-3))
    assert s['scale']['angular_exaggeration']==pytest.approx(scale/(corner[2]/r))
    assert s['tx_corners'][0][0]>corner[0] and s['tx_corners'][0][1]<corner[1]
    json.dumps(s,allow_nan=False)


def test_visual_data_conserves_domain_power_and_uses_real_pixel_layout(data):
    c,a,o,s=data
    assert sum(cell['fraction'] for cell in s['tx_cells'])==pytest.approx(1)
    assert sum(cell['power_w'] for cell in s['tx_cells'])==pytest.approx(c.system.tx.pulse_average_power_w)
    assert max(cell['relative_density'] for cell in s['tx_cells'])==1
    assert len(s['detector_cells'])==c.system.spad.channels_h*c.system.spad.channels_v*c.system.spad.spads_per_channel
    assert all(0<=cell['relative_energy']<=1 for cell in s['detector_cells'])


def test_display_limits_do_not_change_physics_or_fabricate_pixels(data):
    c,a,o,s=data
    b=budget_schematic(c,o,a.model_copy(update={'budget_schematic_max_cells':10}))
    assert b['tx_cells']==[] and b['detector_cells']==[]
    assert b['tx_corners']==s['tx_corners'] and b['rx_corners']==s['rx_corners']
    assert len(b['display_notes'])>=2
    assert b['components']==s['components']


def test_no_overlap_suppresses_return_animation():
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',{
        'geometry':{'vfov_deg':1},
        'system':{'tx':{'tx_center_h_mrad':20},'spad':{'channels_v':16,'H_binning':2,'V_binning':2}}})
    _,_,o=project_illumination(c.system,a,lambda *_:None,lambda:False)
    s=budget_schematic(c,o,a)
    assert not s['return_path_available']
    assert len(s['animation_path'])==3
    assert o['budget']['signal_sensor_incident_photons_per_pulse']==0


def test_parameter_bindings_resolve_to_canonical_config(data):
    c,a,o,s=data
    values=c.model_dump()
    for comp in s['components']:
        for path in comp['paths']:
            val=values
            for key in path.split('.'):val=val[key]

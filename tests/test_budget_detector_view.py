import math
from types import SimpleNamespace
import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.rx.spatial import image_angles, image_center
from spad_lidar.system_budget import calculate_budget
from spad_lidar.reporting.budget_detector_view import detector_view


@pytest.mark.parametrize('mode',['inverted','same'])
def test_pixel_inverse_roundtrip_with_anisotropic_focus_and_offset(mode):
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',{},a)
    r=c.system.rx.model_copy(update={'mapping_mode':mode,'focal_length_h_mm':13,'focal_length_v_mm':27,
                                    'rx_offset_x_um':31,'rx_offset_y_um':-19})
    x=np.array([-80.,0.,60.]);y=np.array([-40.,10.,100.]);h,v=image_angles(r,x,y)
    xx,yy=image_center(r,h,v)
    np.testing.assert_allclose(xx,x,atol=1e-12);np.testing.assert_allclose(yy,y,atol=1e-12)


def test_dual_view_matches_budget_and_remains_independent_of_rx_box():
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',{'geometry':{'vfov_deg':10,'tx_h_width_mrad':3},
        'rx_channel':{'h_width_mrad':6},'system':{'spad':{'channels_v':10,'H_binning':3,'V_binning':4,'pixel_pitch_um':20},
        'rx':{'rx_offset_x_um':15}}},a)
    result=calculate_budget(c,a);v=result['schematic']['views']['detector_view'];single=result['single_channel']
    assert v['cell_count']==12 and len(v['cells'])==12
    assert v['detector_h_um']==60 and v['detector_v_um']==80
    assert v['rx_bounds']['h_min']==-3 and v['rx_bounds']['h_max']==3
    assert v['binning_bounds']['h_min']==pytest.approx(-1000*math.atan(15/20000))
    assert v['binning_bounds']['h_max']==pytest.approx(1000*math.atan(45/20000))
    b=single['optical_budget']
    assert v['capture_fraction']==pytest.approx(b['sensor_signal_j']/b['after_filter_fullplane_signal_j'])
    diffs=np.diff([t['angle_mrad'] for t in v['ticks']]);np.testing.assert_allclose(diffs,v['tick_step_mrad'])
    r=SimpleNamespace(**single['configuration']['rx'])
    for t in v['ticks']:
        x,y=image_center(r,t['angle_mrad'],t['angle_mrad'])
        assert t['image_x_um']==pytest.approx(float(x));assert t['image_y_um']==pytest.approx(float(y))
    # Rx acceptance changes must not resize physical cells or silently align them.
    single['configuration']['rx']['rx_angle_h_min_mrad']=-9
    dataset={'x_edges_um':v['pixel_x_edges_um'],'y_edges_um':v['pixel_y_edges_um']}
    changed=detector_view(single,dataset,a)
    assert changed['binning_bounds']==v['binning_bounds'];assert changed['cells']==v['cells']
    assert changed['rx_bounds']['h_min']==-9
    single['configuration']['rx']['focal_length_h_mm']*=2
    focused=detector_view(single,dataset,a)
    assert focused['detector_h_um']==changed['detector_h_um']
    assert focused['binning_bounds']['h_max']<changed['binning_bounds']['h_max']
    limited=detector_view(single,dataset,a.model_copy(update={'budget_schematic_max_cells':2}))
    assert limited['cells_omitted'] and not limited['cells']
    assert limited['binning_bounds']==focused['binning_bounds']

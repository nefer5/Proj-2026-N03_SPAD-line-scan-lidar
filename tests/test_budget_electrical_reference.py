import math
import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.system_budget import calculate_budget
from spad_lidar.numerics.ideal_irf import IdealIRF
from spad_lidar.constants import C,FWHM_TO_SIGMA


def calc(overrides):
    a=Algorithms.load();c=SimulationConfig.for_experiment('budget',overrides,a)
    return c,calculate_budget(c,a)


def test_histogram_and_range_payload_and_link_grouping():
    c,r=calc({'system':{'spad':{'channels_v':10}},'targets':{'slot_count':100}})
    e=r['electrical'];h=e['formats']['histogram'];p=e['formats']['points']
    assert e['chip_count']==e['link_count']==10
    assert h['total_bytes_per_column']==10*(math.ceil(r['metrics']['histogram_bins']*c.transport.histogram_count_bits/8)+c.electrical.chip_header_bytes)
    assert p['total_bytes_per_column']==10*(c.transport.point_bytes+c.electrical.chip_header_bytes)
    assert h['bytes_per_frame']==h['total_bytes_per_column']*100


def test_average_pass_can_need_buffer_and_low_bandwidth_blocks_frame():
    base={'system':{'readout':{'tdc_bin_ps':20},'spad':{'channels_v':1}},'targets':{'slot_count':100},'transport':{'histogram_count_bits':16,'column_header_bytes':16}}
    _,r=calc(base);s=r['electrical']['selected']
    assert s['average_bandwidth_ok'] and s['frame_ok'] and not s['no_backlog']
    assert s['peak_buffer_bytes_per_link']>s['link_bytes_per_column'][0]
    assert s['timeline'][-1]['end_ns']==pytest.approx(s['frame_completion_ns'])
    _,slow=calc({**base,'electrical':{'lane_rate_mbps':100}})
    assert not slow['electrical']['selected']['frame_ok']


def test_unknown_output_spec_is_not_zero_and_measurement_sets_are_separate():
    _,r=calc({'transport':{'histogram_count_bits':None},'range_reference':{'manual_points':[{'distance_m':100,'area_counts':12,'peak_counts':None,'fwhm_ns':None,'range_std_mm':None,'range_bias_mm':None}], 'measurement_mode':'csv'}})
    assert not r['electrical']['formats']['histogram']['complete']
    assert r['range_reference']['measurements']==[]


@pytest.mark.parametrize('shape',['gaussian','rectangular'])
def test_ideal_irf_normalized_and_inverse_square_area(shape):
    irf=IdealIRF(shape,2000,200)
    assert irf.cdf(100)-irf.cdf(-100)==pytest.approx(1)
    assert irf.pdf(0)>0 and irf.fwhm_ns()>=2
    _,r=calc({'system':{'tx':{'pulse_shape':shape}},'range_reference':{'min_range_m':50,'max_range_m':150,'points':3}})
    a,b,c=r['range_reference']['points']
    assert a['signal_area_counts']/b['signal_area_counts']==pytest.approx(4)
    assert a['irf_fwhm_ns']==b['irf_fwhm_ns']==c['irf_fwhm_ns']


def test_gaussian_signal_only_fisher_matches_shot_noise_limit():
    _,r=calc({'system':{'spad':{'spad_jitter_fwhm_ps':0,'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0},'readout':{'other_jitter_fwhm_ps':0,'tdc_bin_ps':1},'background':{'solar_enabled':False,'other_light_enabled':False}},'range_reference':{'points':3,'min_range_m':50,'max_range_m':150}})
    p=r['range_reference']['current'];expected=C*.5e-6*(2/FWHM_TO_SIGMA)/math.sqrt(p['signal_area_counts'])
    assert p['precision_crlb_mm']==pytest.approx(expected,rel=1e-5)


def test_measurement_csv_rejects_unknown_columns_and_preserves_optional_fields():
    from spad_lidar.webapi.budget import measurements
    from fastapi import HTTPException
    points=measurements('distance_m,area_counts\n100,25\n')
    assert points[0]['distance_m']==100 and points[0]['area_counts']==25
    assert points[0]['range_std_mm'] is None
    assert measurements('')==[]
    with pytest.raises(HTTPException):measurements('distance_m,wrong\n100,12\n')
    with pytest.raises(HTTPException):measurements('distance_m,area_counts\n100,NaN\n')

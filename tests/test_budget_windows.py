import math
import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.system_budget import calculate_budget


def result(overrides):
    a=Algorithms.load()
    c=SimulationConfig.for_experiment('budget',overrides,a)
    return c,calculate_budget(c,a)


@pytest.mark.parametrize('shape',['gaussian','rectangular'])
def test_channel_window_energy_and_candidate_conservation(shape):
    c,r=result({'system':{'tx':{'pulse_shape':shape},'acquisition':{'laser_shots':3}}})
    p=r['channel_photons'];gate,width,intersection=p['windows'];n=c.system.spad.channels_v
    expected=math.erf(math.sqrt(math.log(2))) if shape=='gaussian' else 1
    assert p['width_energy_fraction']==pytest.approx(expected)
    assert p['tx_width_energy_nj']==pytest.approx(r['metrics']['channel_energy_nj']*expected)
    assert width['signal_candidates']==pytest.approx(r['single_channel']['optical_budget']['signal_candidate_avalanches_per_pulse']*expected)
    assert gate['signal_candidates']*n*3==pytest.approx(r['metrics']['signal_candidates_per_column'])
    assert gate['background_candidates']*n*3==pytest.approx(r['metrics']['background_candidates_per_column'])
    assert gate['device_noise_candidates']*n*3==pytest.approx(r['metrics']['device_noise_candidates_per_column'])
    assert intersection['signal_candidates']==pytest.approx(width['signal_candidates'])
    assert np.trapezoid(p['profile']['power_w'],p['profile']['offset_ns'])==pytest.approx(p['tx_total_energy_nj'],rel=1e-8)


def test_window_background_uses_its_own_duration_and_empty_gate_overlap():
    c,r=result({'system':{'acquisition':{'gate_start_ns':100,'gate_width_ns':64}}})
    gate,width,intersection=r['channel_photons']['windows']
    assert intersection['duration_ns']==0 and intersection['signal_candidates']==0
    assert intersection['background_candidates']==0
    assert width['background_candidates']/gate['background_candidates']==pytest.approx(width['duration_ns']/gate['duration_ns'])
    assert all(window['final_mixed_records'] is None for window in [gate,width,intersection])


def test_photon_window_shared_steps_bind_every_value():
    _,r=result({})
    for window in r['channel_photons']['windows']:
        for step in window['flow']:
            assert step['latex'] and step['symbols']
            for value in step['values']:
                assert value['value']==window[value['key']]


def test_signal_chain_uses_single_channel_core_and_candidate_is_not_energy():
    _,r=result({})
    stages=r['channel_photons']['signal_chain']['stages']
    b=r['single_channel']['optical_budget']
    optical=[s for s in stages if s['kind']=='optical']
    assert all(s['energy_nj']==pytest.approx(b[s['key']]*1e9) for s in optical)
    assert optical[0]['energy_nj']==pytest.approx(r['metrics']['channel_energy_nj'])
    assert stages[-1]['energy_nj'] is None
    assert stages[-1]['photons_or_candidates']==pytest.approx(b['signal_candidate_avalanches_per_pulse'])
    assert all(a['energy_nj']>=b['energy_nj'] for a,b in zip(optical,optical[1:]))


def test_all_slot_preview_times_are_inside_active_scan_and_last_finishes_at_scan_end():
    c,r=result({'targets':{'slot_count':100}})
    t=r['timing'];rows=t['frame_preview_slots']
    assert rows[-1]['index']==99
    assert rows[-1]['end_ns']==pytest.approx(t['scan_allocatable_ns'])
    assert rows[-1]['end_ns']<t['frame_period_ns']
    assert all(0<=row['start_ns']<row['end_ns']<=t['scan_allocatable_ns'] for row in rows)

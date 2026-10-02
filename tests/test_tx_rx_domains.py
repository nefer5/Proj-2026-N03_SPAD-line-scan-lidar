from copy import deepcopy
import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,yaml_snapshot,frozen_yaml
from spad_lidar.experiments.spatial import project_illumination,optical_dataset
from spad_lidar.system_budget import calculate_budget
from spad_lidar.tx.angular import vertical_partition
from spad_lidar.legacy_config import migrate_budget


def project(overrides,a=None):
    a=Algorithms.load() if a is None else a
    c=SimulationConfig.for_experiment('system',overrides,a)
    return c,project_illumination(c,a,lambda *_:None,lambda:False)


def test_tx_width_and_power_do_not_change_rx_background():
    _,(light,_,info)=project({})
    _,(changed,_,other)=project({'tx':{'angle_h_min_mrad':-1,'angle_h_max_mrad':1,
        'angle_v_min_mrad':-1,'angle_v_max_mrad':1,'pulse_average_power_w':0}})
    assert changed.signal_photons_per_pulse.sum()==0
    assert np.array_equal(changed.background_photons_per_second,light.background_photons_per_second)
    assert other['budget']['background_angular_domain']==info['budget']['background_angular_domain']
    assert other['budget']['solar_candidate_rate_cps']==info['budget']['solar_candidate_rate_cps']


def test_rx_domain_solid_angle_and_uniform_receiver_scaling():
    common={'rx':{'rx_model':'uniform_pixel'}}
    _,(_,_,info)=project(common)
    _,(_,_,larger)=project({'rx':{'rx_model':'uniform_pixel','rx_angle_h_min_mrad':-12,'rx_angle_h_max_mrad':12}})
    assert larger['budget']['angular_solid_angle_sr']==pytest.approx(2*info['budget']['angular_solid_angle_sr'])
    assert larger['budget']['solar_candidate_rate_cps']==pytest.approx(2*info['budget']['solar_candidate_rate_cps'])
    assert larger['budget']['signal_candidate_avalanches_per_pulse']==pytest.approx(info['budget']['signal_candidate_avalanches_per_pulse'])


def test_tx_outside_acceptance_is_loss_not_renormalization():
    _,(_,_,info)=project({'tx':{'tx_model':'uniform','angle_h_min_mrad':10,'angle_h_max_mrad':12}})
    b=info['budget']
    assert b['tx_angular_coverage_fraction']==pytest.approx(1)
    assert b['tx_domain_output_j']>0 and b['signal_sensor_incident_photons_per_pulse']==0
    assert b['rx_loss_j']==pytest.approx(b['rx_pupil_signal_j'])


def test_imported_rx_coverage_is_checked_separately():
    a=Algorithms.load();c=SimulationConfig.for_experiment('system',{})
    data=optical_dataset(c,a).model_dump()
    with pytest.raises(ValueError,match='full configured acceptance'):
        project({'rx':{'rx_model':'dataset','dataset':data,'rx_angle_h_min_mrad':-20,'rx_angle_h_max_mrad':20}})


def test_uniform_v_partition_conserves_energy():
    p=vertical_partition([-3,-1,1,3],[1/3,1/3,1/3],16)
    assert p['fractions']==pytest.approx([1/16]*16)
    assert sum(p['fractions'])==pytest.approx(1)


def test_power_duration_and_old_energy_migration():
    c=SimulationConfig.for_experiment('system',{})
    assert c.tx.pulse_average_power_w==280
    assert c.tx.total_pulse_energy_nj==560
    old=SimulationConfig.for_experiment('system',{'tx':{'total_pulse_energy_nj':12,'pulse_fwhm_ps':2000}})
    assert old.tx.pulse_average_power_w==6 and old.tx.total_pulse_energy_nj==12
    wide=SimulationConfig.for_experiment('system',{'tx':{'pulse_fwhm_ps':4000}})
    assert wide.tx.total_pulse_energy_nj==1120
    with pytest.raises(ValueError,match='Do not mix'):
        SimulationConfig.for_experiment('system',{'tx':{'pulse_average_power_w':280,'total_pulse_energy_nj':12}})


def test_vfov_links_tx_only_and_v_rows_sum_to_total():
    a=Algorithms.load()
    c=SimulationConfig.for_experiment('budget',{
        'geometry':{'vfov_deg':1,'tx_h_width_mrad':2},
        'rx_channel':{'v_width_deg':None},
        'system':{'tx':{'pulse_average_power_w':280,'pulse_fwhm_ps':2000}}})
    assert c.system.tx.angle_h_max_mrad-c.system.tx.angle_h_min_mrad==2
    assert c.system.tx.angle_v_max_mrad-c.system.tx.angle_v_min_mrad==pytest.approx(np.deg2rad(1)*1000)
    assert c.system.rx.rx_angle_v_max_mrad==pytest.approx(np.deg2rad(1)*1000/2)  # blank per-channel V follows Tx
    r=calculate_budget(c,a);rows=r['vertical_budget']['rows']
    assert sum(row['tx_energy_nj'] for row in rows)==pytest.approx(560)
    assert sum(row['tx_pulse_average_power_w'] for row in rows)==pytest.approx(280)
    assert sum(row['signal_candidates_per_column'] for row in rows)==pytest.approx(r['metrics']['signal_candidates_per_column'])
    assert sum(row['background_candidates_per_column'] for row in rows)==pytest.approx(r['metrics']['background_candidates_per_column'])


def test_missing_power_default_is_not_hidden_by_override():
    snap=deepcopy(yaml_snapshot());snap['defaults.yaml']['experiments']['system']['tx'].pop('pulse_average_power_w')
    with frozen_yaml(snap),pytest.raises(ValueError):
        SimulationConfig.for_experiment('system',{'tx':{'pulse_average_power_w':280}})


def test_budget_v1_migration_preserves_domain_and_energy():
    c=SimulationConfig.for_experiment('budget',{}).model_dump();c.pop('geometry')
    tx=c['system']['tx'];tx.pop('pulse_average_power_w');tx['total_pulse_energy_nj']=12
    tx.update(angle_h_min_mrad=-6,angle_h_max_mrad=6)
    migrated=SimulationConfig.for_experiment('budget',migrate_budget(c))
    assert migrated.system.tx.total_pulse_energy_nj==12
    assert migrated.geometry.tx_h_width_mrad==12

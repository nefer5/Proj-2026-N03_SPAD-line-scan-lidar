import copy
import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.constants import C
from spad_lidar.scan.trajectory import mirror_pose,angle_bin_index,angle_bin_edges
from spad_lidar.scan.schedule import build_schedule
from spad_lidar.scene.scan_target import reflection_range
from spad_lidar.experiments.scanning import run_scan
from spad_lidar.experiments.spatial import run_system
from spad_lidar.processing.scan_reconstruction import reconstruct_scan

noop=lambda *x:None
never=lambda:False


def cfg(overrides=None):
    from spad_lidar.curves import merge_config
    from spad_lidar.legacy_config import migrate_experiment_overrides
    example=read_yaml('defaults.yaml')['experiments']['scan_demo']
    return SimulationConfig.for_experiment('scan',merge_config(example,migrate_experiment_overrides('scan',{} if overrides is None else overrides)))


def run(overrides=None,algorithms=None):
    return run_scan(cfg(overrides),Algorithms.load() if algorithms is None else algorithms,noop,never)


def test_frame_budget_real_dwell_and_blanked_flyback():
    c=cfg();a=Algorithms.load();program,rows,edges,budget=build_schedule(c,a)
    result=run_scan(c,a,noop,never);s=result['scan']
    assert budget['scheduled_slots']==100
    assert s['summary']['emitted_reference_slots']==80
    assert s['summary']['blanked_slots']==20
    assert s['frame_budget']['actual_emissions_in_time_window']==80
    assert s['frame_budget']['center_accounted_tx_output_energy_j']==pytest.approx(80*9.6e-9)
    assert s['frame_budget']['actual_tx_average_power_w']==pytest.approx(79.5*9.6e-9/.001)
    assert s['assigned_pulses_per_frame_bin']==[[4]*20]
    assert s['true_useful_pulses_per_frame_bin']==[[4]*20]
    assert s['uniform_forward_dwell_reference_per_bin']==pytest.approx([4]*20)
    assert sum(map(sum,s['assigned_pulses_per_frame_bin']))==80
    assert np.sum(s['histogram_cube_counts'])==s['summary']['retained_records']
    assert s['summary']['retained_records']+sum(s['summary']['excluded_records'].values())==len(result['records'])


@pytest.mark.parametrize('mode',[m for m in read_yaml('readout-modes.yaml') if m!='analytic_reference'])
@pytest.mark.parametrize('initial_condition',['fully_recovered','periodic_history'])
def test_static_scan_reduces_exactly_to_b_records_and_histogram(mode,initial_condition):
    c=cfg({'scan':{'trajectory':'static'},'readout':{'readout_mode':mode}})
    # Compare the same initial condition, not new cold-start B against historical
    # continuous-scan prehistory. Both conditions must preserve exact core parity.
    a=Algorithms.load().model_copy(update={'b_initial_condition':initial_condition})
    if initial_condition=='fully_recovered':a=a.model_copy(update={'readout_warmup_cycles':0})
    out=run_scan(c,a,noop,never)
    from spad_lidar.experiments.system_config import form_values
    same=form_values(c);same.pop('scan');same.pop('scene_motion');same['timing']['laser_shots']=sum(r['measured'] for r in out['scan']['schedule']) if 'measured' in out['scan']['schedule'][0] else len(out['scan']['schedule'])
    b=SimulationConfig.for_experiment('system',same)
    reference=run_system(b,a,noop,never)
    assert out['records']==reference['records']
    assert out['histogram']==reference['histogram']
    assert np.array_equal(np.array(out['scan']['histogram_cube_counts']).sum(axis=(0,1)),reference['histogram']['counts'])


def test_mechanical_mapping_and_continuous_return_pose():
    c=cfg();r=run_scan(c,Algorithms.load(),noop,never);s=r['scan']
    pulse=next(p for p in s['pulse_optical_audit'] if p['emitted'])
    row=s['schedule'][pulse['cycle']]
    assert row['true_tx_optical_mrad']==pytest.approx(row['mechanical_angle_mrad']*c.scan.optical_multiplier+c.scan.optical_offset_mrad)
    echoes=np.array(pulse['ray_echo_time_ns'])
    _,axis,_,_=mirror_pose(c.scan,echoes)
    assert np.allclose(pulse['rx_pointing_at_echo_mrad'],axis)
    h=np.array(r['optics']['angular_h_centers_mrad'])
    relative=h+row['true_tx_optical_mrad']-axis
    assert np.allclose(pulse['ray_relative_rx_h_mrad'],relative)
    assert np.max(np.abs(relative-h))>0


def test_half_open_angular_edges_and_short_final_bin():
    c=cfg({'scan':{'angle_bin_width_mrad':3}})
    edges=angle_bin_edges(c.scan,Algorithms.load().max_scan_angle_bins)
    assert edges[-1]==20 and edges[-1]-edges[-2]==1
    assert angle_bin_index([-21,-20,-17,20],edges).tolist()==[-1,0,1,-1]


def test_detector_state_is_not_reset_at_angle_or_frame_boundaries():
    options={'scan':{'frame_count':2},'device':{'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0,
        'spad_dead_time_ns':2e6},'optics':{'total_pulse_energy_nj':100},'readout':{'readout_mode':'independent_multi'}}
    a=Algorithms.load().model_copy(update={'readout_warmup_cycles':0})
    r=run(options,a)
    n=cfg(options).device.spads_per_channel*cfg(options).optics.channels_h*cfg(options).optics.channels_v
    assert r['audit']['final_records']<=n
    assert r['audit']['spad_dead_losses']>0
    options['device']['spad_dead_time_ns']=0
    available=run(options,a)
    assert available['audit']['final_records']>n


def test_encoder_error_changes_assignment_but_not_photons_or_records():
    reference=run();delayed=run({'scan':{'encoder_latency_ns':1000}})
    assert reference['records']==delayed['records']
    assert reference['histogram']==delayed['histogram']
    assert reference['scan']['assigned_pulses_per_frame_bin']!=delayed['scan']['assigned_pulses_per_frame_bin']
    assert reference['scan']['true_useful_pulses_per_frame_bin']==delayed['scan']['true_useful_pulses_per_frame_bin']
    row=next(r for r in delayed['scan']['schedule'] if r['cycle']==10)
    assert row['encoder_angle_error_mrad']==pytest.approx(-.05)


def test_laser_time_error_is_not_removed_using_hidden_truth():
    base={'scan':{'trajectory':'static'},'device':{'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0}}
    first=run(base);base['scan']['laser_time_offset_ns']=10
    shifted=run(base)
    left=[r for r in first['scan']['range_rows'] if r['raw_distance_m'] is not None]
    right=[r for r in shifted['scan']['range_rows'] if r['raw_distance_m'] is not None]
    assert len(left)==len(right)>0
    for a,b in zip(left,right):
        assert b['raw_distance_m']-a['raw_distance_m']==pytest.approx(C*10e-9/2,abs=1e-10)
        assert b['source_weighted_range_m']==pytest.approx(a['source_weighted_range_m'])


@pytest.mark.parametrize('trajectory',['triangle','sinusoidal'])
def test_nonuniform_and_bidirectional_scans_count_discrete_pulses(trajectory):
    r=run({'scan':{'trajectory':trajectory}});s=r['scan']
    assert s['summary']['emitted_reference_slots']==100
    assert s['uniform_forward_dwell_reference_per_bin'] is None
    assert sum(map(sum,s['actual_emissions_per_frame_bin']))+s['summary']['outside_true_angle']==100
    if trajectory=='sinusoidal':
        assert len(set(s['actual_emissions_per_frame_bin'][0]))>1


def test_last_partial_frame_gate_and_zero_exposure_are_reported():
    r=run({'scan':{'trajectory':'static','frame_rate_hz':1e9/1500},'timing':{'gate_start_ns':1600,'gate_width_ns':2000}})
    assert r['scan']['frame_budget']['scheduled_slots']==1
    assert r['scan']['recording_gate_exposure_s']==0
    assert r['scan']['summary']['gate_truncated_ns']==2000
    assert r['records']==[]
    assert all(row['raw_distance_m'] is None for row in r['scan']['range_rows'])


def test_scene_motion_interception_and_gradient_components():
    c=cfg({'scene_motion':{'radial_velocity_m_s':10,'range_gradient_m_per_rad':50}})
    ranges=reflection_range(c.optics,c.scene_motion,np.array([-10,10]),1e6)
    assert np.allclose(ranges,np.array([99.51,100.51])/(1-10/C))
    r=run_scan(c,Algorithms.load(),noop,never)
    first=next(p for p in r['scan']['signal_components'] if p['arrival_centers_ns'])
    assert len(first['arrival_centers_ns'])==Algorithms.load().spatial_angle_samples_h
    assert max(first['arrival_centers_ns'])>min(first['arrival_centers_ns'])
    assert r['scan']['point_cloud']
    for point in r['scan']['point_cloud']:
        assert np.linalg.norm([point['x_m'],point['y_m'],point['z_m']])==pytest.approx(point['raw_distance_m'])


def test_no_extrapolation_when_fixed_rx_has_insufficient_coverage():
    with pytest.raises(ValueError,match='extrapolation'):
        run({'scan':{'rx_scan_scale':0}})
    r=run({'scan':{'rx_scan_scale':0},'optics':{'rx_angle_h_min_mrad':-30,'rx_angle_h_max_mrad':30}})
    assert r['scan']['pulse_optical_audit']


def test_seed_reproducibility_block_invariance_and_replay():
    c=cfg({'scan':{'laser_jitter_std_ns':1}});a=Algorithms.load()
    first=run_scan(c,a,noop,never)
    second=run_scan(c,a.model_copy(update={'acquisition_block_cycles':1}),noop,never)
    assert first['records']==second['records']
    assert first['scan']==second['scan']
    s=first['scan'];truth={int(k):{n:np.array(v) for n,v in row.items()} for k,row in s['source_truth_by_cycle'].items()}
    coarse=reconstruct_scan(c,a,first['records'],s['warmup_schedule']+s['schedule'],np.array(s['angle_edges_mrad']),s['channel_directions_mrad'],truth,2000)
    assert np.sum(coarse['histogram_cube_counts'])==np.sum(s['histogram_cube_counts'])
    assert coarse['assigned_pulses_per_frame_bin']==s['assigned_pulses_per_frame_bin']


def test_reconstruction_never_uses_truth_to_estimate_range():
    c=cfg();a=Algorithms.load();r=run_scan(c,a,noop,never);s=r['scan']
    wrong={int(k):{n:np.array(v) for n,v in row.items()} for k,row in s['source_truth_by_cycle'].items()}
    for row in wrong.values():row['range_weighted']*=10
    changed=reconstruct_scan(c,a,r['records'],s['warmup_schedule']+s['schedule'],np.array(s['angle_edges_mrad']),s['channel_directions_mrad'],wrong)
    assert [p['raw_distance_m'] for p in changed['range_rows']]==[p['raw_distance_m'] for p in s['range_rows']]


def test_scan_resources_and_unknown_independent_shot_count_rejected():
    with pytest.raises(ValueError):cfg({'timing':{'laser_shots':999}})
    with pytest.raises(ValueError):cfg({'scan':{'frame_count':1000000}})
    with pytest.raises(ValueError):cfg({'scan':{'angle_bin_width_mrad':1e-12}})


def test_scan_preview_api_and_parameter_documentation():
    client=TestClient(app);c=cfg()
    assert client.get('/system/scan').status_code==200
    preview=client.post('/api/experiments/scan/preview',json={})
    assert preview.status_code==200
    r=run();p=preview.json()
    assert p['assigned_pulses_per_frame_bin']==r['scan']['assigned_pulses_per_frame_bin']
    assert p['true_useful_pulses_per_frame_bin']==r['scan']['true_useful_pulses_per_frame_bin']
    help=read_yaml('parameter-help.yaml')['experiments']
    for group in ('scan','scene_motion'):
        for key in type(getattr(c,group)).model_fields:
            assert all(k in help[group+'.'+key] for k in ('label','unit','description'))
    assert client.post('/api/experiments/scan/validate',json={'scan':{'trajectory':None}}).status_code==422


def test_scan_replay_and_point_cloud_export_http(monkeypatch):
    r=run()
    class StoredResult:
        def result(self,job_id):return r
    import spad_lidar.webapi.labs as api
    monkeypatch.setattr(api,'manager',lambda:StoredResult())
    client=TestClient(app)
    replay=client.post('/api/jobs/test/scan-replay',json={'bin_ps':2000})
    assert replay.status_code==200
    assert replay.json()['summary']['retained_records']==r['scan']['summary']['retained_records']
    assert client.post('/api/jobs/test/scan-replay',json={'bin_ps':500}).status_code==422
    csv=client.get('/api/jobs/test/point-cloud.csv')
    assert csv.status_code==200
    assert len(csv.text.splitlines())==len(r['scan']['point_cloud'])+1
    assert 'x_m,y_m,z_m' in csv.text.splitlines()[0]
    import csv as csv_module,io
    coarse_csv=client.get('/api/jobs/test/point-cloud.csv?bin_ps=2000')
    point=next(csv_module.DictReader(io.StringIO(coarse_csv.text)))
    assert float(point['processing_bin_ps'])==2000
    assert float(point['raw_distance_m'])==replay.json()['point_cloud'][0]['raw_distance_m']


def test_roundoff_policy_is_explicit_and_does_not_change_optical_angles():
    from spad_lidar.scan.trajectory import snap_angle_roundoff
    edges=np.array([-2.,0.,2.])
    original=np.array([-1e-14,1.9])
    snapped,delta=snap_angle_roundoff(original,edges,1e-12)
    assert original[0]==-1e-14 and snapped[0]==0 and delta[0]==1e-14
    assert angle_bin_index(snapped,edges).tolist()==[1,1]
    assert angle_bin_index(original,edges).tolist()==[0,1]
    with pytest.raises(ValueError):snap_angle_roundoff(original,edges,1)


def test_complete_legacy_b_config_preserves_coupled_rx_coverage():
    from spad_lidar.experiments.system_config import form_values
    old=form_values(SimulationConfig.for_experiment('system',{}))
    for key in list(old['optics']):
        if key.startswith('rx_angle_'):old['optics'].pop(key)
    old['optics']['angle_h_min_mrad']=-10
    old['optics']['angle_h_max_mrad']=10
    migrated=SimulationConfig.for_experiment('system',old)
    assert migrated.optics.rx_angle_h_min_mrad==-10 and migrated.optics.rx_angle_h_max_mrad==10


def test_b_configuration_transfer_keeps_optics_but_recomputes_scan_pulse_budget():
    client=TestClient(app)
    transferred=client.post('/api/experiments/scan/from-system',json={'optics':{'range_m':75},'timing':{'laser_shots':5}})
    assert transferred.status_code==200
    config=transferred.json()['experiment']
    assert config['scene']['range_m']==75
    assert 'laser_shots' not in config['acquisition']
    preview=client.post('/api/experiments/scan/preview',json=config).json()
    assert preview['frame_budget']['scheduled_slots']==100


@pytest.mark.parametrize('shape',['gaussian','rectangular'])
def test_tx_power_uses_temporal_energy_integral_not_full_pulse_count(shape):
    from spad_lidar.numerics.temporal import pulse_interval_fractions
    assert pulse_interval_fractions([0.],0,100,shape,2000)[0]==pytest.approx(.5)
    assert pulse_interval_fractions([50.],0,100,shape,2000)[0]==pytest.approx(1)
    r=run({'scan':{'trajectory':'static'},'optics':{'pulse_shape':shape}})
    assert r['scan']['frame_budget']['actual_tx_output_energy_j']<r['scan']['frame_budget']['center_accounted_tx_output_energy_j']

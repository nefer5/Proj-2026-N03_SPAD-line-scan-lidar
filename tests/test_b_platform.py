from copy import deepcopy
import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml,frozen_yaml,yaml_snapshot
from spad_lidar.experiments.system_config import form_values
from spad_lidar.experiments.spatial import project_illumination,optical_dataset
from spad_lidar.experiments.spatial_analysis import run_system_analysis,replay_analysis
from spad_lidar.reporting.spatial_view import channel_db_tables
from spad_lidar.rx.spatial import image_center
from spad_lidar.adapters.optical_data import validate_dataset

quiet=lambda *args:None
never=lambda:False


def test_domain_defaults_and_roundtrip_are_shared_with_a():
    a=SimulationConfig();b=SimulationConfig.for_experiment('system',{})
    assert set(b.model_dump())=={'tx','scene','rx','spad','readout','background','acquisition','spectral_inputs'}
    assert b.acquisition.laser_shots==a.laser_shots
    assert b.acquisition.monte_carlo_trials==a.monte_carlo_trials
    assert b.background.solar_enabled==a.solar_enabled
    assert b.background.other_light_enabled==a.other_light_enabled
    assert b.tx.total_pulse_energy_nj==a.pulse_energy_nj
    assert b.spectral_inputs==a.spectral_inputs
    assert SimulationConfig.for_experiment('system',form_values(b)).model_dump()==b.model_dump()
    assert SimulationConfig.for_experiment('system',b.model_dump()).model_dump()==b.model_dump()


@pytest.mark.parametrize('override',[{'rx':{'focal_length_h_mm':0}}, {'rx':{'focal_length_v_mm':float('nan')}},
    {'rx':{'unknown':1}}, {'spad':{'spads_per_channel':99}}, {'acquisition':{'monte_carlo_trials':-1}},
    {'rx':{'mapping_mode':1}}, {'optics':{'focal_length_mm':20,'focal_length_h_mm':20}},
    {'tx':{},'optics':{'range_m':100}}])
def test_invalid_and_mixed_configs_rejected(override):
    with pytest.raises(ValueError):SimulationConfig.for_experiment('system',override)


def test_missing_domain_default_not_filled_by_user_override():
    snapshot=yaml_snapshot();snapshot['defaults.yaml']['experiments']['system']['rx'].pop('focal_length_h_mm')
    with frozen_yaml(snapshot),pytest.raises(ValueError):
        SimulationConfig.for_experiment('system',{'rx':{'focal_length_h_mm':20}})


def test_legacy_scalar_focal_preserves_orientation_and_converts_vertical_coordinates():
    c=SimulationConfig.for_experiment('system',{'optics':{'focal_length_mm':30,'tx_center_v_mrad':1,
        'rx_offset_y_um':5,'angle_v_min_mrad':-1,'angle_v_max_mrad':2}})
    assert c.rx.focal_length_h_mm==c.rx.focal_length_v_mm==30
    assert c.rx.mapping_mode=='legacy_upright'
    assert c.tx.tx_center_v_mrad==-1 and c.rx.rx_offset_y_um==-5
    assert (c.tx.angle_v_min_mrad,c.tx.angle_v_max_mrad)==(-2,1)


def test_anamorphic_focals_and_inverted_psf_energy():
    c=SimulationConfig.for_experiment('system',{'rx':{'focal_length_h_mm':40,'focal_length_v_mm':10}})
    angle=np.arctan(.001)*1000
    x,y=image_center(c.optics,angle,angle)
    assert x==pytest.approx(-40) and y==pytest.approx(-10)
    _,_,info=project_illumination(c,Algorithms.load(),quiet,never)
    from spad_lidar.reporting.spatial_view import optical_view
    view=optical_view(c,Algorithms.load(),info);p=np.array(view['angle_psfs'])
    assert np.all(p.sum(axis=(1,2))<=1+Algorithms.load().energy_conservation_rtol)
    idx=np.argmin((np.array(info['angular_h_centers_mrad'])-.7)**2+(np.array(info['angular_v_centers_mrad'])-.7)**2)
    xe=np.array(view['x_edges_um']);ye=np.array(view['y_edges_um'])
    assert p[idx].sum(axis=0)@((xe[:-1]+xe[1:])/2)<0
    assert p[idx].sum(axis=1)@((ye[:-1]+ye[1:])/2)<0


def test_readout_layout_uses_acquisition_groups_and_actual_pixel_edges():
    # Regression: the reported 1x8 / 16x4 form must not retain an old 8x32 layout.
    from spad_lidar.reporting.readout_layout import readout_layout
    c=SimulationConfig.for_experiment('system',{'spad':{'channels_h':1,'channels_v':8,'H_binning':16,'V_binning':4}})
    _,groups,info=project_illumination(c,Algorithms.load(),quiet,never)
    layout=readout_layout(info)
    assert (layout['pixels_h'],layout['pixels_v'],layout['total_channels'],layout['spads_per_channel'])==(16,32,8,64)
    assert sum(ch['spad_count'] for ch in layout['channels'])==layout['total_pixels']==512
    for channel in layout['channels']:
        assert channel['spad_count']==int((groups==channel['id']).sum())
        assert channel['id']==channel['v']*layout['channels_h']+channel['h']
    # An imported Rx table can use nonuniform coordinates: display those actual
    # boundaries, never reconstruct a second geometry from a nominal pixel pitch.
    info['dataset']['rx']['x_edges_um'][0]=-173.0
    info['dataset']['rx']['y_edges_um'][-1]=347.0
    changed=readout_layout(info)
    assert changed['channels'][0]['x_um'][0]==-173.0
    assert changed['channels'][0]['y_um'][1]<changed['channels'][-1]['y_um'][0]
    assert changed['channels'][-1]['y_um'][-1]==347.0


def test_gaussian_far_tail_is_not_cancellation_zero():
    from spad_lidar.rx.spatial import normal_bin_mass
    right=normal_bin_mass(np.array([8.,9.]))[0]
    left=normal_bin_mass(np.array([-9.,-8.]))[0]
    assert right>0 and right==left


def test_optical_v1_axis_migration_preserves_energy_and_reindexes():
    a=Algorithms.load();b=SimulationConfig.for_experiment('system',{})
    original=optical_dataset(b,a).model_dump();legacy=deepcopy(original)
    legacy['schema_version']=1;legacy['coordinate_convention']='optical_H_right_V_down__image_x_right_y_down'
    legacy['tx']['v_edges_mrad']=(-np.array(original['tx']['v_edges_mrad'])[::-1]).tolist()
    legacy['tx']['energy_fraction']=np.array(original['tx']['energy_fraction'])[::-1].tolist()
    rx=legacy['rx'];old=original['rx']
    rx['v_angle_mrad']=(-np.array(old['v_angle_mrad'])[::-1]).tolist()
    rx['y_edges_um']=(-np.array(old['y_edges_um'])[::-1]).tolist()
    rx['collection_efficiency']=np.array(old['collection_efficiency'])[:,::-1,:].tolist()
    rx['psf_pixel_fraction']=np.array(old['psf_pixel_fraction'])[:,::-1,:,::-1,:].tolist()
    migrated=validate_dataset(legacy,a).model_dump()
    assert migrated['schema_version']==2
    assert migrated['tx']==original['tx'] and migrated['rx']==original['rx']
    assert 'coordinate_migration' in migrated['provenance']


def test_energy_db_definition_and_zero_reference():
    ratios=channel_db_tables([[1,.1,.01,0]])['matrix_db'][0]
    assert ratios[1][0]==-10 and ratios[2][0]==-20 and ratios[0][1]==10
    assert ratios[3][0]=='-inf' and ratios[3][3] is None and ratios[0][3] is None


@pytest.fixture(scope='module')
def analysis():
    cfg=SimulationConfig.for_experiment('system',{'background':{'solar_enabled':False,'other_light_enabled':False},
        'acquisition':{'laser_shots':2,'monte_carlo_trials':3}})
    a=Algorithms.load().model_copy(update={'readout_expected_trials':2})
    return cfg,a,run_system_analysis(cfg,a,quiet,never)


def test_repeats_use_shared_records_and_independent_roles(analysis):
    cfg,a,r=analysis
    assert r['statistics']['trial_histograms'][0]==r['histogram']['counts']
    assert len(r['statistics']['trial_histograms'])==3
    assert set(r['statistics']['trial_seeds']).isdisjoint(r['statistics']['noise_seeds'])
    assert r['statistics']['trial_seeds'][0]==cfg.rng_seed
    again=run_system_analysis(cfg,a,quiet,never)
    assert r['records']==again['records'] and r['statistics']==again['statistics']
    assert sum(x['full_signal_total'] for x in r['references'])==pytest.approx(cfg.timing.laser_shots*r['optics']['budget']['signal_candidate_avalanches_per_pulse'])


def test_replay_rebins_every_replicate_and_keeps_original(analysis):
    cfg,a,r=analysis;before=deepcopy(r)
    coarse=replay_analysis(r,cfg,a,2*cfg.readout.tdc_bin_ps)
    expected=np.add.reduceat(np.array(r['statistics']['trial_histograms']),np.arange(0,len(r['histogram']['time_ns']),2),axis=-1)
    assert coarse['statistics']['trial_histograms']==expected.tolist()
    assert coarse['statistics']['lower']==expected.min(axis=0).tolist()
    assert np.sum(coarse['histogram']['counts'])==len(r['records'])
    assert r==before
    with pytest.raises(ValueError):replay_analysis(r,cfg,a,cfg.readout.tdc_bin_ps/2)


def test_zero_repeat_and_cancellation():
    c=SimulationConfig.for_experiment('system',{'acquisition':{'monte_carlo_trials':0},
        'background':{'solar_enabled':False,'other_light_enabled':False}})
    a=Algorithms.load().model_copy(update={'readout_expected_trials':1})
    r=run_system_analysis(c,a,quiet,never)
    assert r['statistics']['lower'] is None and r['statistics']['trial_histograms']==[]
    with pytest.raises(InterruptedError):run_system_analysis(c,a,quiet,lambda:True)


def test_analysis_resource_limits(analysis):
    cfg,a,_=analysis
    with pytest.raises(ValueError,match='histogram'):
        run_system_analysis(cfg,a.model_copy(update={'max_lab_analysis_histogram_cells':1}),quiet,never)


def test_live_api_preview_config_and_shared_formula_contracts():
    client=TestClient(app);catalog=client.get('/api/experiments/system').json()
    assert catalog['schema_version']==3 and 'rx' in catalog['defaults']
    response=client.post('/api/experiments/system/preview',json={'rx':{'focal_length_h_mm':30}})
    assert response.status_code==200
    view=response.json();assert 'records' not in view
    assert len(view['parameter_figures'])==10
    assert view['form_configuration']['optics']['focal_length_h_mm']==30
    assert view['parameter_figures']['timing']['focus_window_ns'][0]>0
    for key,latex in view['formulas'].items():assert latex==read_yaml('formulas.yaml')[key]
    for version in (2,3):
        envelope={'schema_version':version,'kind':'system','experiment':catalog['defaults']}
        assert client.post('/api/experiments/system/import',content=__import__('json').dumps(envelope),headers={'Content-Type':'text/plain'}).status_code==200
    assert client.get('/system').headers['cache-control']=='no-store'
    assert '/static/shared/histogram-window.js?v=' in client.get('/system').text
    assert '/static/shared/histogram-window.js?v=' in client.get('/').text

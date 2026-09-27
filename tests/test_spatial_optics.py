from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import photon_budget
from spad_lidar.experiments.spatial import project_illumination,optical_dataset,run_system
from spad_lidar.adapters.optical_data import validate_dataset,RxTable
from spad_lidar.contracts import CandidateEvents
from spad_lidar.spad import AcquisitionSession
from spad_lidar.timing import periodic_program

noop=lambda *args:None
never=lambda:False


def cfg(overrides=None):
    return SimulationConfig.for_experiment('system',{} if overrides is None else overrides)


def project(c):
    return project_illumination(c,Algorithms.load(),noop,never)


def test_spatial_energy_conservation_and_explicit_edge_loss():
    c=cfg();light,groups,info=project(c);b=info['budget']
    assert np.asarray(info['signal_energy_per_pixel_j']).sum()==pytest.approx(b['sensor_signal_j'])
    assert b['rx_pupil_signal_j']==pytest.approx(b['sensor_signal_j']+b['rx_loss_j']+b['filter_loss_j']+b['psf_edge_loss_j'],rel=1e-12,abs=0)
    assert b['tx_angular_coverage_fraction']==pytest.approx(1)
    assert b['tx_angular_truncation_j']==0
    assert b['tx_domain_output_j']==pytest.approx(c.optics.total_pulse_energy_nj*1e-9*c.optics.tx_efficiency)
    assert b['target_incident_j']==pytest.approx(b['tx_domain_output_j']*c.optics.atmospheric_one_way_transmission)
    assert b['psf_edge_loss_j']>0
    assert np.bincount(groups).tolist()==[c.device.spads_per_channel]*(c.optics.channels_h*c.optics.channels_v)
    shifted=project(cfg({'optics':{'rx_offset_x_um':300}}))[2]['budget']
    assert shifted['after_filter_fullplane_signal_j']==b['after_filter_fullplane_signal_j']
    assert shifted['sensor_signal_j']<b['sensor_signal_j']
    assert shifted['psf_edge_loss_j']>b['psf_edge_loss_j']


@pytest.mark.parametrize('tx_model',['uniform','gaussian'])
def test_single_channel_uniform_receiver_matches_a_all_reference_planes(tx_model):
    a=SimulationConfig()
    c=cfg({'optics':{'tx_model':tx_model,'rx_model':'uniform_pixel','channels_h':1,'channels_v':1,
        'total_pulse_energy_nj':a.pulse_energy_nj,
        'angle_h_min_mrad':-a.channel_ifov_h_mrad/2,'angle_h_max_mrad':a.channel_ifov_h_mrad/2,
        'angle_v_min_mrad':-a.channel_ifov_v_mrad/2,'angle_v_max_mrad':a.channel_ifov_v_mrad/2,
        'solar_enabled':True,'other_light_enabled':True}})
    light,_,info=project(c);b=info['budget'];reference=photon_budget(a)
    for key in ('signal_rx_incident_photons_per_pulse','signal_sensor_incident_photons_per_pulse',
                'solar_rx_incident_photons_per_gate','other_rx_incident_photons_per_gate',
                'solar_sensor_incident_photons_per_gate','other_sensor_incident_photons_per_gate'):
        assert b[key]==pytest.approx(getattr(reference,key),rel=1e-12,abs=0),key
    assert b['signal_candidate_avalanches_per_pulse']==pytest.approx(reference.signal_detected_per_pulse,rel=1e-12)
    assert b['solar_candidate_avalanches_per_gate']==pytest.approx(reference.solar_detected_per_gate,rel=1e-12)
    assert b['other_candidate_avalanches_per_gate']==pytest.approx(reference.other_light_detected_per_gate,rel=1e-12)
    assert np.allclose(light.signal_photons_per_pulse,light.signal_photons_per_pulse[0])


def test_dataset_roundtrip_retains_nonuniform_photons_and_record_realization():
    a=Algorithms.load();c=cfg({'timing':{'laser_shots':2}})
    data=optical_dataset(c,a).model_dump()
    imported=cfg({'timing':{'laser_shots':2},'optics':{'tx_model':'dataset','rx_model':'dataset','dataset':data}})
    first=run_system(c,a,noop,never);second=run_system(imported,a,noop,never)
    assert first['illumination']['signal_photons_per_pixel_per_pulse']==second['illumination']['signal_photons_per_pixel_per_pulse']
    assert first['records']==second['records']
    assert first['optics']['budget']==second['optics']['budget']


def test_zero_pde_has_no_optical_candidates_and_no_records_without_dark_counts():
    c=cfg({'device':{'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0},
           'spectral_inputs':{'pde':{'mode':'basic','basic':{'shape':'constant','amplitude':0}}}})
    r=run_system(c,Algorithms.load(),noop,never)
    assert r['records']==[]
    assert r['optics']['budget']['signal_sensor_incident_photons_per_pulse']>0
    assert r['optics']['budget']['signal_candidate_avalanches_per_pulse']==0


def test_dataset_does_not_silently_clip_or_renormalize():
    a=Algorithms.load();data=optical_dataset(cfg(),a).model_dump()
    data['tx']['energy_fraction'][0][0]=2
    with pytest.raises(ValueError,match='unity'):
        validate_dataset(data,a)
    data=optical_dataset(cfg(),a).model_dump()
    data['rx']['psf_pixel_fraction'][0][0][0][0][0]=2
    with pytest.raises(ValueError,match='unity'):
        validate_dataset(data,a)
    data=optical_dataset(cfg(),a).model_dump()
    data['rx']['collection_efficiency'][0][0][0]=float('nan')
    with pytest.raises(ValueError):
        validate_dataset(data,a)


def test_imported_tx_is_explicitly_normalized_but_rx_edge_loss_is_retained():
    a=Algorithms.load();c=cfg();original=optical_dataset(c,a).model_dump()
    data=deepcopy(original)
    data['tx']['energy_fraction']=(np.asarray(data['tx']['energy_fraction'])*.2).tolist()
    imported=cfg({'tx':{'tx_model':'dataset'},'rx':{'rx_model':'dataset','dataset':data}})
    light,_,info=project(imported)
    reference=project(c)
    assert info['tx_energy_normalization']['input_fraction_sum']==pytest.approx(.2)
    assert np.asarray(info['tx_energy_fraction']).sum()==pytest.approx(1)
    np.testing.assert_allclose(light.signal_photons_per_pulse,reference[0].signal_photons_per_pulse,rtol=1e-12)
    assert info['dataset']['rx']==original['rx']
    assert info['budget']['psf_edge_loss_j']==pytest.approx(reference[2]['budget']['psf_edge_loss_j'])
    data['tx']['energy_fraction']=np.zeros_like(data['tx']['energy_fraction']).tolist()
    with pytest.raises(ValueError,match='positive'):
        validate_dataset(data,a)


def test_narrow_domain_redistributes_entire_pulse_without_changing_background():
    c=cfg({'tx':{'tx_fwhm_h_mrad':16,'tx_fwhm_v_mrad':6,'angle_v_min_mrad':-1,'angle_v_max_mrad':1}})
    light,_,info=project(c)
    b=info['budget']
    assert b['target_incident_j']==pytest.approx(c.tx.total_pulse_energy_nj*1e-9*c.tx.tx_efficiency*c.scene.atmospheric_one_way_transmission)
    from scipy.special import ndtr
    from spad_lidar.constants import FWHM_TO_SIGMA
    o=c.optics;h=np.array(info['tx_h_edges_mrad']);v=np.array(info['tx_v_edges_mrad'])
    raw=np.outer(np.diff(ndtr((v-o.tx_center_v_mrad)/(o.tx_fwhm_v_mrad/FWHM_TO_SIGMA))),
                 np.diff(ndtr((h-o.tx_center_h_mrad)/(o.tx_fwhm_h_mrad/FWHM_TO_SIGMA))))
    np.testing.assert_allclose(info['tx_energy_fraction'],raw/raw.sum(),rtol=1e-12)
    assert raw.sum()<.2  # Regression for the user's wide Gaussian / narrow V-domain case.
    uniform=project(cfg({'tx':{**c.tx.model_dump(),'tx_model':'uniform'}}))
    np.testing.assert_array_equal(light.background_photons_per_second,uniform[0].background_photons_per_second)


def test_gaussian_positive_tail_remains_normalizable_and_empty_weights_fail():
    from spad_lidar.tx.angular import gaussian_axis_fractions,normalize_angular_weights
    edges=np.linspace(10,11,12)
    fractions=gaussian_axis_fractions(edges,0,1)
    assert np.all(np.isfinite(fractions)) and np.all(fractions>0)
    assert fractions.sum()==pytest.approx(1)
    np.testing.assert_allclose(fractions,gaussian_axis_fractions(-edges[::-1],0,1)[::-1])
    with pytest.raises(ValueError,match='cannot normalize'):
        normalize_angular_weights([0,0])


def test_linear_interpolation_at_angle_and_wavelength_midpoints():
    a=Algorithms.load();data=optical_dataset(cfg(),a).model_dump();rx=data['rx']
    rx.update(wavelength_nm=[900,910],h_angle_mrad=[-1,1],v_angle_mrad=[-1,1])
    n=(len(rx['x_edges_um'])-1)*(len(rx['y_edges_um'])-1)
    values=np.empty((2,2,2));psf=np.empty((2,2,2,len(rx['y_edges_um'])-1,len(rx['x_edges_um'])-1))
    for w in range(2):
        for v in range(2):
            for h in range(2):
                values[w,v,h]=(1+w+v+h)/10
                psf[w,v,h]=1/n
    rx['collection_efficiency']=values.tolist();rx['psf_pixel_fraction']=psf.tolist()
    table=RxTable(validate_dataset(data,a).rx)
    eff,p=table.evaluate(905,[0],[0])
    assert eff[0]==pytest.approx(.25)
    assert p.sum()==pytest.approx(1)
    with pytest.raises(ValueError,match='extrapolation'):
        table.evaluate(920,[0],[0])


@pytest.mark.parametrize('mode',['independent_multi','shared_multi','coincidence_sliding'])
def test_independent_channel_groups_do_not_interfere(mode):
    c=cfg({'readout':{'readout_mode':mode}});n=c.device.spads_per_channel
    program=periodic_program(100,0,100,0,1,1)
    single=AcquisitionSession(c.device,c.readout,np.zeros(n,dtype=int),program,100)
    multi=AcquisitionSession(c.device,c.readout,np.repeat([0,1],n),program,100)
    single.advance(CandidateEvents([10,11,20],[0,1,0]),100)
    multi.advance(CandidateEvents([10,11,20,10,11,20],[0,1,0,n,n+1,n]),100)
    left=[r for r in multi.readout.records if r['channel']==0]
    assert left==single.readout.records
    assert multi.stats['recorded']==2*single.stats['recorded']


def test_all_spatial_parameters_documented_and_formulas_share_definitions():
    c=cfg();help=read_yaml('parameter-help.yaml')
    for key in type(c.optics).model_fields:
        meta=help['experiments'].get('optics.'+key,help.get(key))
        assert meta and all(k in meta for k in ('label','unit','description')),key
    r=run_system(c,Algorithms.load(),noop,never)
    formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    for step in r['photon_flow']['steps']:
        assert step['latex']==formulas[step['formula_id']]
        assert step['symbols']==notes[step['formula_id']]
    assert r['photon_flow']['background_integration_band_nm']==[855,955]


def test_system_http_contracts_and_duplicate_import_validation():
    client=TestClient(app)
    r=client.get('/api/experiments/system')
    assert r.status_code==200
    assert client.get('/system').status_code==200
    dataset=client.post('/api/experiments/system/optical-data',json={})
    assert dataset.status_code==200
    assert dataset.json()['synthetic'] is True
    invalid=client.post('/api/optics/validate',content='schema_version: 1\nschema_version: 1',headers={'Content-Type':'text/plain'})
    assert invalid.status_code==422


def test_background_is_independent_of_tx_energy_and_shape():
    override={'timing':{'laser_shots':1},'optics':{'solar_enabled':True,'solar_illuminance_lux':100,
              'other_light_enabled':True,'other_light_scale':0.001}}
    light,_,info=project(cfg(override))
    override['optics'].update(total_pulse_energy_nj=0,tx_fwhm_h_mrad=1)
    darklight,_,darkinfo=project(cfg(override))
    assert darklight.signal_photons_per_pulse.sum()==0
    assert np.array_equal(light.background_photons_per_second,darklight.background_photons_per_second)
    b=info['budget']
    assert b['solar_rx_incident_photons_per_gate']>=b['solar_after_rx_photons_per_gate']>=b['solar_after_filter_fullplane_photons_per_gate']>=b['solar_sensor_incident_photons_per_gate']>0
    assert b['other_rx_incident_photons_per_gate']>=b['other_sensor_incident_photons_per_gate']>0


def test_spatial_resource_guard_precedes_large_grid_allocation():
    a=Algorithms.load().model_copy(update={'spatial_angle_samples_h':10**12})
    with pytest.raises(ValueError,match='before allocation'):
        project_illumination(cfg(),a,noop,never)

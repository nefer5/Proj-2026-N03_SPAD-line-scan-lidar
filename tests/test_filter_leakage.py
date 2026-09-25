from copy import deepcopy
import numpy as np
import pytest
from scipy.integrate import quad
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,yaml_snapshot,frozen_yaml
from spad_lidar.curves import Curve
from spad_lidar.spectra import spectral_components
from spad_lidar.experiments.spatial import project_illumination,system_program,optical_dataset
from spad_lidar.experiments.lab import run_illumination
from spad_lidar.contracts import SensorIllumination
from spad_lidar.contracts.spectral_product import SpectralProduct,zero_spectral
from spad_lidar.reporting.background_bins import background_bin_values


@pytest.mark.parametrize('shape',['constant','rectangle','gaussian','cosine_flat'])
def test_every_basic_filter_has_bounded_out_of_band_and_correct_integral(shape):
    cfg=SimulationConfig(spectral_inputs={'filter':{'mode':'basic','basic':{'shape':shape,'out_of_band_transmission':.002}}})
    curve=Curve(cfg.spectral_inputs.filter);b=cfg.spectral_inputs.filter.basic
    assert curve(400)==pytest.approx(.002)
    assert curve(1200)==pytest.approx(.002)
    assert curve(b.center_nm)==pytest.approx(b.amplitude)
    lo,hi=400,1200
    expected=quad(curve,lo,hi,points=curve.knots(),limit=200,epsabs=1e-10)[0]
    assert curve.integral_nm([lo,hi])==pytest.approx(expected,rel=1e-9)
    assert np.all((curve(np.linspace(lo,hi,1001))>=.002)&(curve(np.linspace(lo,hi,1001))<=b.amplitude))


def test_csv_bank_ignores_basic_leakage_and_other_curve_types_reject_it():
    points=[{'wavelength_nm':900,'value':.2},{'wavelength_nm':910,'value':.2}]
    cfg=SimulationConfig(spectral_inputs={'filter':{'mode':'csv','csv_points':points,'basic':{'out_of_band_transmission':.1}}})
    curve=Curve(cfg.spectral_inputs.filter)
    assert curve([800,905,1000]).tolist()==[0,.2,0]
    assert curve.integral_nm()==pytest.approx(2)
    with pytest.raises(ValueError):SimulationConfig(spectral_inputs={'pde':{'basic':{'out_of_band_transmission':.1}}})
    for value in (-.1,1.1,float('nan')):
        with pytest.raises(ValueError):SimulationConfig(spectral_inputs={'filter':{'basic':{'out_of_band_transmission':value}}})


def test_broadband_leakage_includes_the_provided_solar_spectrum():
    base=SimulationConfig();old=spectral_components(base)
    cfg=SimulationConfig(spectral_inputs={'filter':{'basic':{'out_of_band_transmission':.001}}})
    leaked=spectral_components(cfg,plot=True)
    assert old['budget_band_nm']==[855,955]
    assert leaked['budget_band_nm']==[280,4000]
    assert leaked['solar_detectable_photons_s_m2_sr']>old['solar_detectable_photons_s_m2_sr']
    x=np.asarray(leaked['integration']['wavelength_nm']);t=np.asarray(leaked['integration']['filter_transmission'])
    assert np.all(t[(x<855)|(x>955)]==.001)


def test_factorized_measure_matches_dense_and_same_engine_sampling():
    a=Algorithms.load();cfg=SimulationConfig.for_experiment('system',{
        'spectral_inputs':{'filter':{'basic':{'out_of_band_transmission':.001}}},
        'acquisition':{'laser_shots':1}})
    light,groups,info=project_illumination(cfg,a,lambda *_:None,lambda:False)
    assert isinstance(light.background_photons_per_second,SpectralProduct)
    assert info['spectral_integration']['storage']=='outer_product'
    assert info['spectral_integration']['stored_cells_per_measure']<info['spectral_integration']['logical_cells']
    response=Curve(cfg.spectral_inputs.pde)(light.wavelength_nm)
    dense=light.background_photons_per_second.dense()
    np.testing.assert_allclose(light.background_photons_per_second@response,dense@response,rtol=1e-12)
    np.testing.assert_allclose(light.background_photons_per_second.sum(axis=1),dense.sum(axis=1),rtol=1e-12)
    assert np.all((zero_spectral(light.signal_photons_per_pulse)@response)==0)
    source=SensorIllumination(light.wavelength_nm,light.signal_photons_per_pulse.dense(),dense,light.pulse_shape,light.pulse_fwhm_ps,light.pulse_delay_ns,light.provenance)
    first=run_illumination(cfg,a,light,groups,lambda *_:None,lambda:False,program=system_program(cfg,a))
    second=run_illumination(cfg,a,source,groups,lambda *_:None,lambda:False,program=system_program(cfg,a))
    assert first['records']==second['records']


def test_factorized_optical_integrals_match_wavelength_by_wavelength_projection():
    a=Algorithms.load();cfg=SimulationConfig.for_experiment('system',{
        'spad':{'channels_h':1,'channels_v':1,'H_binning':1,'V_binning':1},
        'spectral_inputs':{'filter':{'basic':{'out_of_band_transmission':.001}}}})
    fast=project_illumination(cfg,a,lambda *_:None,lambda:False)
    dense=project_illumination(cfg,a.model_copy(update={'factorize_achromatic_leakage':False}),lambda *_:None,lambda:False)
    np.testing.assert_allclose(fast[0].background_photons_per_second.dense(),dense[0].background_photons_per_second,rtol=1e-12)
    for key in ('solar_sensor_incident_photons_per_gate','solar_candidate_avalanches_per_gate','other_sensor_incident_photons_per_gate','solar_mean_candidates_per_time_bin'):
        assert fast[2]['budget'][key]==pytest.approx(dense[2]['budget'][key],rel=1e-12)


def test_bin_value_is_only_candidate_rate_times_bin_duration():
    assert background_bin_values(2e9,3e8,500)['solar_mean_candidates_per_time_bin']==pytest.approx(1)
    a=Algorithms.load();base=SimulationConfig.for_experiment('system',{})
    changed=SimulationConfig.for_experiment('system',{'acquisition':{'gate_width_ns':1024,'laser_shots':8,'monte_carlo_trials':3}})
    first=project_illumination(base,a,lambda *_:None,lambda:False)[2]['budget']
    second=project_illumination(changed,a,lambda *_:None,lambda:False)[2]['budget']
    for source in ('solar','other'):
        key=source+'_mean_candidates_per_time_bin'
        assert first[key]==pytest.approx(second[key],rel=1e-12)
        assert first[key]==pytest.approx(first[source+'_candidate_rate_cps']*base.readout.tdc_bin_ps*1e-12)


def test_old_filter_schema_migrates_and_missing_default_is_rejected():
    old=SimulationConfig().model_dump();old['spectral_inputs']['filter']['basic'].pop('out_of_band_transmission')
    assert SimulationConfig.model_validate(old).spectral_inputs.filter.basic.out_of_band_transmission==0
    snap=yaml_snapshot();snap['defaults.yaml']['simulation']['spectral_inputs']['filter']['basic'].pop('out_of_band_transmission')
    with frozen_yaml(snap),pytest.raises(ValueError):SimulationConfig(spectral_inputs={'filter':{'basic':{'out_of_band_transmission':0}}})
    client=TestClient(app)
    result=client.post('/api/curve/validate?kind=filter',json=old['spectral_inputs']['filter'])
    assert result.status_code==200 and result.json()['basic']['out_of_band_transmission']==0


def test_imported_rx_limits_are_explicit_and_dark_signal_needs_no_broadband_table():
    from types import SimpleNamespace
    from spad_lidar.spectra import background_spectral_domain
    a=Algorithms.load();cfg=SimulationConfig.for_experiment('system',{})
    dataset=optical_dataset(cfg,a).model_dump()
    # The original Rx supports 855..955 nm; full source coverage is not invented.
    imported=SimulationConfig.for_experiment('system',{'rx':{'rx_model':'dataset','dataset':dataset},
        'spectral_inputs':{'filter':{'basic':{'out_of_band_transmission':.001}}}})
    proxy=SimpleNamespace(**imported.optics.model_dump(),spectral_inputs=imported.spectral_inputs)
    domain=background_spectral_domain(proxy,a)
    assert domain['band_nm']==[855,955] and domain['requested_band_nm']==[280,4000]
    assert domain['rx_coverage_limited'] is True
    proxy.solar_enabled=False;proxy.other_light_enabled=False
    proxy.dataset=deepcopy(dataset);proxy.dataset['rx']['wavelength_nm']=[905]
    assert background_spectral_domain(proxy,a)['rx_coverage_limited'] is False


def test_filter_plot_focus_does_not_limit_the_background_integral():
    from spad_lidar.reporting.a_view import filter_profile
    cfg=SimulationConfig(spectral_inputs={'filter':{'basic':{'out_of_band_transmission':.001}}})
    fig=filter_profile(cfg)
    assert fig['integration_domain']['band_nm']==[280,4000]
    assert max(fig['wavelength_nm'])<1200
    assert fig['transmission'][0]==pytest.approx(.001)
    assert fig['weighted_bandwidth_nm']==pytest.approx(13.21)


def test_column_acquisition_accepts_full_spectrum_factored_background():
    from spad_lidar.configuration import read_yaml
    from spad_lidar.curves import merge_config
    from spad_lidar.experiments.columns import run_columns
    values=merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{
        'system_targets':{'slot_count':4},'background':{'solar_enabled':True,'solar_illuminance_lux':1,'other_light_enabled':False},
        'spectral_inputs':{'filter':{'basic':{'out_of_band_transmission':.001}}}})
    cfg=SimulationConfig.for_experiment('columns',values)
    result=run_columns(cfg,Algorithms.load(),lambda *_:None,lambda:False)
    assert result['optics']['spectral_integration']['storage']=='outer_product'
    assert result['audit']['final_records']==len(result['records'])
    assert result['photon_flow']['values']['solar_mean_candidates_per_time_bin']>0

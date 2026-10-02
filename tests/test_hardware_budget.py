import copy
import json
import re
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms, frozen_yaml, yaml_snapshot
from spad_lidar.system_budget import calculate_budget
from spad_lidar.experiments.spatial import project_illumination


@pytest.fixture(scope='module')
def base():
    a=Algorithms.load()
    cfg=SimulationConfig.for_experiment('budget',{},a)
    return cfg,a,calculate_budget(cfg,a)


def run(values,a):
    return calculate_budget(SimulationConfig.for_experiment('budget',values,a),a)


def test_default_sources_and_unknowns(base):
    cfg,a,r=base
    reference=SimulationConfig.for_experiment('system',{},a)
    assert cfg.system.spad.channels_v==reference.spad.channels_v
    assert cfg.system.spad.channels_h==1
    assert cfg.system.rx.rx_aperture_width_mm==reference.rx.rx_aperture_width_mm
    assert cfg.system.tx.pulse_average_power_w==reference.tx.pulse_average_power_w
    assert cfg.system.tx.angle_h_max_mrad-cfg.system.tx.angle_h_min_mrad==2
    assert cfg.targets==SimulationConfig.system_targets({})
    assert r['metrics']['time_margin_us'] is None
    assert r['metrics']['final_mixed_records'] is None
    assert r['metrics']['electric_power_w'] is None
    assert r['metrics']['physical_spads']==r['metrics']['channels']*cfg.system.spad.H_binning*cfg.system.spad.V_binning
    final=[v for s in r['photon_flow']['steps'] for v in s['values'] if v['key']=='final_mixed_records']
    assert final and final[0]['value'] is None
    json.dumps(r,allow_nan=False)


def test_shared_b_optics_and_energy_conservation(base):
    cfg,a,r=base
    single=SimulationConfig.for_experiment('system',r['single_channel']['configuration'],a)
    _,_,b=project_illumination(single,a,lambda *args:None,lambda:False)
    assert r['single_channel']['optical_budget']==b['budget']
    assert r['optical_budget']['signal_candidate_avalanches_per_pulse']==pytest.approx(b['budget']['signal_candidate_avalanches_per_pulse']*cfg.system.spad.channels_v)
    budget=r['optical_budget']
    assert budget['rx_pupil_signal_j']==pytest.approx(sum(budget[k] for k in ('sensor_signal_j','rx_loss_j','filter_loss_j','psf_edge_loss_j')))
    assert sum(r['channel_sensor_photons_per_pulse'])==pytest.approx(budget['signal_sensor_incident_photons_per_pulse'])


def test_multishot_and_power_dimensional_scaling(base):
    cfg,a,one=base
    four=run({'system':{'acquisition':{'laser_shots':4}},'assumptions':{'reset_time_ns':1000,'wall_plug_efficiency':.25}},a)
    m=four['metrics'];u=one['metrics']
    assert m['column_energy_nj']==4*u['column_energy_nj']
    assert m['average_optical_power_w']==pytest.approx(4*u['average_optical_power_w'])
    assert m['signal_candidates_per_column']==pytest.approx(4*u['signal_candidates_per_column'])
    assert m['background_candidates_per_column']==pytest.approx(4*u['background_candidates_per_column'])
    assert m['electric_power_w']==pytest.approx(m['average_optical_power_w']/.25)
    assert m['emitter_heat_w']+m['average_optical_power_w']==pytest.approx(m['electric_power_w'])
    assert m['time_margin_us']==pytest.approx(m['column_time_us']-m['acquisition_envelope_us']-1)
    assert m['max_frame_rate_hz']>cfg.targets.frame_rate_hz
    assert four['provenance']['configuration_sha256']!=one['provenance']['configuration_sha256']


def test_oversubscribed_column_and_hardware_link(base):
    _,a,_=base
    r=run({'system':{'acquisition':{'laser_shots':8}},'assumptions':{'reset_time_ns':0},
        'transport':{'histogram_count_bits':16,'column_header_bytes':0,'mipi_net_mbps':1},'electrical':{'capacity_mode':'aggregate_net','chip_header_bytes':0}},a)
    states={c['id']:c['status'] for c in r['constraints']}
    assert states['timing']=='fail' and states['link']=='fail'
    m=r['metrics']
    assert m['max_pulses_per_column']==7
    assert m['histogram_payload_bytes']==m['histogram_bins']*m['channels']*2
    assert m['average_payload_mbps']==pytest.approx(m['histogram_payload_bytes']*8*1000*10/1e6)


def test_zero_energy_and_out_of_gate_limit(base):
    _,a,_=base
    r=run({'system':{'tx':{'total_pulse_energy_nj':0},'scene':{'range_m':1000}}},a)
    assert r['metrics']['signal_candidates_per_column']==0
    assert r['metrics']['average_optical_power_w']==0
    assert r['metrics']['background_candidates_per_column']>0
    assert next(c for c in r['constraints'] if c['id']=='gate')['status']=='fail'


def test_prbs_is_independent_budget_not_fictitious_gain(base):
    _,a,r0=base
    r=run({'assumptions':{'prbs_enabled':True,'prbs_chip_count':127,'prbs_on_count':64,'prbs_chip_ns':10}},a)
    assert r['metrics']==r0['metrics']
    assert r['prbs']['period_ns']==1270
    assert r['prbs']['energy_nj']==64*r['metrics']['single_pulse_energy_nj']
    assert r['prbs']['nominal_periodic_range_m']==pytest.approx(190.36821083)


@pytest.mark.parametrize('override',[
    {'assumptions':{'reset_time_ns':-1}}, {'assumptions':{'reset_time_ns':float('nan')}},
    {'assumptions':{'wall_plug_efficiency':float('inf')}}, {'assumptions':{'wall_plug_efficiency':0}},
    {'assumptions':{'wall_plug_efficiency':1.01}}, {'assumptions':{'prbs_enabled':True}},
    {'assumptions':{'prbs_chip_count':3.5}}, {'assumptions':{'prbs_enabled':True,'prbs_chip_count':3,'prbs_on_count':4,'prbs_chip_ns':1}},
    {'targets':{'slot_count':True}}, {'system':{'acquisition':{'period_ns':1}}},
    {'assumptions':{'mystery':0}}, {'mystery':1},
])
def test_bad_config_fails(override):
    with pytest.raises(ValueError):SimulationConfig.for_experiment('budget',override)


def test_missing_default_not_filled_by_override():
    snapshot=copy.deepcopy(yaml_snapshot())
    snapshot['defaults.yaml']['experiments']['budget'].pop('reset_time_ns')
    with frozen_yaml(snapshot),pytest.raises(ValueError):
        SimulationConfig.for_experiment('budget',{'assumptions':{'reset_time_ns':0}})


def test_default_reload_without_python_restart():
    snapshot=copy.deepcopy(yaml_snapshot())
    snapshot['defaults.yaml']['experiments']['budget']['reset_time_ns']=250
    with frozen_yaml(snapshot):assert SimulationConfig.for_experiment('budget',{}).assumptions.reset_time_ns==250
    assert SimulationConfig.for_experiment('budget',{}).assumptions.reset_time_ns is None


def test_api_content_hashes_no_cache_import_errors_and_round_trip():
    with TestClient(app) as client:
        page=client.get('/system/budget')
        assert page.headers['cache-control']=='no-store'
        assets=re.findall(r'(?:src|href)="(/static/[^\"]+)"',page.text)
        assert assets and all(re.search(r'\?v=[a-f0-9]{64}$',v) for v in assets)
        for url in assets:assert client.get(url).status_code==200
        catalog=client.get('/api/system-budget').json()
        envelope=dict(schema_version=1,kind='hardware-budget',experiment=catalog['defaults'])
        response=client.post('/api/system-budget/import',content=json.dumps(envelope),headers={'Content-Type':'text/plain'})
        assert response.status_code==200 and response.json()==catalog['defaults']
        for bad in ('schema_version: 1\nschema_version: 2',json.dumps({**envelope,'schema_version':0})):
            assert client.post('/api/system-budget/import',content=bad,headers={'Content-Type':'text/plain'}).status_code==422
        assert client.post('/api/system-budget/calculate',json={'targets':{'bad':1}}).status_code==422


def test_catalog_has_help_for_every_visible_field():
    from spad_lidar.webapi.budget import catalog
    c=catalog();help={}
    def flatten(doc):
        for k,v in doc.items():
            if isinstance(v,dict):
                if 'label' in v:help[k]=v
                else:flatten(v)
    flatten(c['help'])
    for _,prefix,keys in c['groups']:
        for key in keys:
            p=('system_targets' if prefix=='targets' else prefix.removeprefix('system.'))+'.'+key
            assert any(k in help for k in (prefix+'.'+key,p,key))

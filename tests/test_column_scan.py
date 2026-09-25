import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.curves import merge_config
from spad_lidar.scan.column_schedule import build_column_schedule
from spad_lidar.scan.column_optics import yaw_angles
from spad_lidar.scan.transport import transport_plan
from spad_lidar.experiments.columns import run_columns
from spad_lidar.numerics.temporal import temporal_cdf,temporal_pdf


def cfg(values=None):
    values={} if values is None else values
    return SimulationConfig.for_experiment('columns',merge_config(
        merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{'system_targets':{'slot_count':4}}),values))


def test_target_schedule_and_separate_ids():
    c=SimulationConfig.for_experiment('columns',{});p,rows,columns,b=build_column_schedule(c,Algorithms.load())
    assert len(columns)==1000 and b['trigger_count']==4000
    assert columns[1]['start_ns']==pytest.approx(66700)
    assert columns[0]['cycles']==[0,1,2,3]
    assert rows[-1]['frame']==0 and rows[-1]['column']==999
    assert max(r['true_tx_optical_mrad'] for r in rows)>1000
    assert b['gate_union_exposure_ns']==pytest.approx(4000*c.timing.gate_width_ns)


def test_gate_union_and_disconnected_fragments():
    c=cfg({'exposure':{'pulses':[{'time_offset_ns':0,'energy_nj':1},{'time_offset_ns':1000,'energy_nj':1}]}})
    p,rows,_,b=build_column_schedule(c,Algorithms.load().model_copy(update={'readout_warmup_cycles':0}))
    assert p.detector_intervals(p.windows[0])==[(0,1000)]
    assert p.detector_intervals(p.windows[1])==[(1000,3048)]
    assert b['gate_union_exposure_ns']==pytest.approx(4*3048)
    delayed=cfg({'acquisition':{'gate_start_ns':2000,'gate_width_ns':1000},'exposure':{'pulses':[
        {'time_offset_ns':0,'energy_nj':1},{'time_offset_ns':2500,'energy_nj':1}]}})
    p,_,_,_=build_column_schedule(delayed,Algorithms.load().model_copy(update={'readout_warmup_cycles':0}))
    assert p.detector_intervals(p.windows[1])==[(2500,3000),(4500,5500)]
    w=p.locate(4000);assert w.gate_open_ns==w.gate_close_ns
    assert p.locate(4600).cycle==1


def test_wide_yaw_is_reversible_and_vertical_geometry_is_preserved():
    h=np.array([-3.,0.,3.]);v=np.array([2.,-1.,2.]);world_h,world_v=yaw_angles(h,v,60000*np.pi/180)
    restored_h,restored_v=yaw_angles(world_h,world_v,-60000*np.pi/180)
    assert np.allclose(restored_h,h) and np.allclose(restored_v,v)
    assert np.max(np.abs(world_v))>np.max(np.abs(v))


@pytest.mark.parametrize('shape',['gaussian','rectangular'])
def test_tail_is_normalized_and_causal_delay(shape):
    t=np.linspace(-20,200,20001);tail=(.3,15.)
    pdf=temporal_pdf(t,shape,2000,tail)
    assert np.all(pdf>=0)
    assert np.trapezoid(pdf,t)==pytest.approx(1,abs=.002)
    assert temporal_cdf(0,shape,2000,tail)<.5
    assert temporal_cdf(1e6,shape,2000,tail)==pytest.approx(1)


def test_double_buffer_overlap_and_overflow_are_not_duration_sum():
    c=cfg({'system_targets':{'frame_rate_hz':20000,'scan_time_utilization':.8,'slot_count':4},
        'exposure':{'pulses':[{'time_offset_ns':0,'energy_nj':1}]},
        'transport':{'enabled':True,'dsp_time_us':3,'mipi_time_us':4}})
    _,_,columns,_=build_column_schedule(c,Algorithms.load())
    p=transport_plan(c,columns)
    assert p['summary']['dropped_columns']==0
    assert p['rows'][0]['output_latency_ns']==pytest.approx(17000)
    assert p['rows'][0]['output_latency_ns']>c.budget['slot_target_ns']
    assert p['summary']['peak_occupied_buffers']==2
    c=cfg({'system_targets':{'frame_rate_hz':20000,'scan_time_utilization':.8,'slot_count':4},
        'exposure':{'pulses':[{'time_offset_ns':0,'energy_nj':1}]},
        'transport':{'enabled':True,'dsp_time_us':3,'mipi_time_us':30}})
    _,_,columns,_=build_column_schedule(c,Algorithms.load());p=transport_plan(c,columns)
    assert p['status']=='overloaded' and p['summary']['dropped_columns']>0


def test_column_energy_audit_sparse_histograms_and_state_trace():
    c=cfg({'exposure':{'tail_fraction':.2,'tail_tau_ns':30},'transport':{'enabled':True,'dsp_time_us':8,'mipi_time_us':12}})
    r=run_columns(c,Algorithms.load(),lambda *args:None,lambda:False)
    assert r['audit']['final_records']==len(r['records'])>0
    assert r['column_scan']['summary']['column_count']==4
    assert 'histogram_cube_counts' not in r['column_scan']
    assert abs(r['photon_flow']['values']['energy_balance_residual_j'])<1e-20
    flow=r['photon_flow']['values']
    assert flow['reference_tx_domain_output_j']==pytest.approx(flow['reference_tx_input_energy_j']*c.tx.tx_efficiency)
    assert flow['target_incident_j']==pytest.approx(flow['reference_tx_domain_output_j']*c.scene.atmospheric_one_way_transmission)
    assert r['optics']['tx_energy_normalization']['mode']=='within_configured_angular_domain'
    assert r['audit']['device_trace']
    assert r['column_scan']['transport']['summary']['delivered_columns']==4
    assert r['statistics']['trial_count']==1


def test_selected_device_logging_does_not_change_records_and_dead_state_crosses_columns():
    settings={'spad':{'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0,'spad_dead_time_ns':1e9},
        'tx':{'total_pulse_energy_nj':100}}
    a=Algorithms.load().model_copy(update={'readout_warmup_cycles':0})
    first=run_columns(cfg(settings),a,lambda *args:None,lambda:False)
    traced=run_columns(cfg(merge_config(settings,{'diagnostics':{'pixel_id':0}})),a,lambda *args:None,lambda:False)
    assert first['records']==traced['records']
    assert len(first['records'])<=cfg(settings).spad.channels_h*cfg(settings).spad.channels_v*cfg(settings).device.spads_per_channel
    assert first['audit']['spad_dead_losses']>0

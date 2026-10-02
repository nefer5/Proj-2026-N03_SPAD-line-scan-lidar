"""Audit data sizes, real dependencies, finite buffers and CSI wire service."""
import copy
import json
import math
import pytest
from spad_lidar.configuration import Algorithms,frozen_yaml,yaml_snapshot
from spad_lidar.models import SimulationConfig
from spad_lidar.scan.planning import uniform_column_budget
from spad_lidar.electrical_budget import electrical_budget,packet_budget
from spad_lidar.budget_pipeline import schedule_link


def evaluate(overrides):
    a=Algorithms.load();cfg=SimulationConfig.for_experiment('budget',overrides,a)
    t=uniform_column_budget(cfg.targets);t['frame_preview_indices']=list(range(min(3,cfg.targets.slot_count)))
    q=cfg.system.acquisition
    envelope=(q.laser_shots-1)*q.period_ns+max(q.gate_start_ns+q.gate_width_ns,cfg.system.tx.pulse_fwhm_ps/2000)
    return cfg,electrical_budget(cfg,t,envelope,a)


def test_range_complete_point_echo_upper_bound_and_all_formats():
    cfg,e=evaluate({'system':{'spad':{'channels_v':5}},'electrical':{'channels_per_chip':2,'chips_per_link':2,'echo_max_count':3,'echo_max_bins':7,'echo_descriptor_bytes':8},'transport':{'point_bytes':12,'histogram_count_bits':10,'column_header_bytes':13}})
    assert e['channel_counts_per_chip']==[2,2,1]
    p=e['formats']['points'];echo=e['formats']['echo'];h=e['formats']['histogram']
    assert p['body_bytes_per_column']==5*12
    assert echo['body_bytes_per_column']==5*3*(8+math.ceil(7*10/8))
    assert p['header_bytes_per_column']==3*cfg.electrical.chip_header_bytes+2*13
    assert h['pipeline']['dsp_bypassed'] and h['pipeline']['dsp_ns']==0
    assert not p['pipeline']['dsp_bypassed']
    json.dumps(e,allow_nan=False)


def test_csi_long_short_packet_and_lane_rate_units():
    assert packet_budget(65536,65535)==dict(payload_bytes=65536,long_packets=2,long_packet_overhead_bytes=12,wire_bytes=65548,last_payload_bytes=1)
    cfg,e=evaluate({'system':{'spad':{'channels_v':1}},'targets':{'slot_count':3},'electrical':{'data_lanes_per_link':4,'lane_rate_mbps':1500,'payload_efficiency':1,'chip_header_bytes':0,'packet_payload_bytes':4,'line_short_packets':True},'transport':{'payload_format':'points','point_bytes':8,'column_header_bytes':0}})
    p=e['selected']
    assert e['total_raw_mbps']==e['total_net_mbps']==6000
    assert p['link_packets_per_column']==[2]
    assert p['link_wire_bytes_per_column']==[8+2*6+8]
    assert p['wire_bytes_per_frame']==3*28+8
    assert p['wire_ns']==pytest.approx(28*8/6000*1000)
    assert p['pipeline']['rows'][0]['end_ns']-p['pipeline']['rows'][0]['start_ns']==pytest.approx(p['wire_ns']+4*8/6000*1000)


def test_protocol_gaps_not_double_counted_in_efficiency():
    _,e=evaluate({'system':{'spad':{'channels_v':1}},'electrical':{'payload_efficiency':.5,'burst_gap_us':2,'packet_payload_bytes':8}})
    s=e['selected']
    assert s['wire_ns']==pytest.approx(s['link_wire_bytes_per_column'][0]*8/e['net_mbps_per_link']*1000+s['link_packets_per_column'][0]*2000)


def test_fixed_ab_copy_clear_and_fifo_backpressure_matches_dependencies():
    a=Algorithms.load().model_copy(update={'budget_output_fifo_columns':1});cfg=SimulationConfig.for_experiment('budget',{'targets':{'slot_count':3},'electrical':{'hist_copy_us':10,'bank_clear_us':5,'ready_delay_us':0,'dsp_time_us':100,'mipi_pack_us':10}},a)
    timing=dict(frame_period_ns=2000000,scan_allocatable_ns=240000,slot_max_ns=80000,frame_preview_indices=[0,1,2])
    p=schedule_link(cfg,timing,80000,12500,1024,1024,160000,4096,a)
    s0,s1,s2=p['rows']
    assert s0['copy_start_ns']==80000 and s0['copy_end_ns']==90000
    assert s1['capture_start_ns']==95000
    assert s1['copy_start_ns']==s0['commit_ns']==190000
    assert s1['commit_ns']==s0['end_ns']
    assert s2['copy_start_ns']==s1['commit_ns']
    assert p['fifo_wait_max_ns']>0 and p['peak_fifo_bytes']==1024
    assert not p['cadence_ok']
    for row in p['rows']:
        assert row['copy_start_ns']>=row['hist_ready_ns']
        assert row['input_start_ns']==row['copy_end_ns']
        assert row['dsp_start_ns']==row['input_end_ns']
        assert row['commit_ns']>=row['dsp_end_ns']
        assert row['start_ns']>=row['pack_end_ns']
    for prev,nxt in zip(p['rows'],p['rows'][1:]):
        assert nxt['capture_start_ns']>=prev['clear_end_ns']
        assert nxt['copy_start_ns']>=prev['commit_ns']
        assert nxt['start_ns']>=prev['end_ns']


def test_single_reuse_is_serial_and_double_overlaps():
    base={'targets':{'slot_count':3,'scan_time_utilization':1,'frame_rate_hz':10000},'system':{'spad':{'channels_v':1}},'electrical':{'dsp_time_us':80,'bank_clear_us':1}}
    _,double=evaluate(base)
    _,single=evaluate({**base,'electrical':{**base['electrical'],'buffer_architecture':'single'}})
    d=double['selected']['pipeline']['rows'];s=single['selected']['pipeline']['rows']
    assert d[1]['capture_start_ns']<d[0]['dsp_end_ns']
    assert s[1]['capture_start_ns']>=s[0]['commit_ns']+1000
    assert s[0]['copy_start_ns']==s[0]['copy_end_ns']


def test_fixed_cross_frame_latency_is_not_accumulating_throughput_loss():
    _,e=evaluate({'targets':{'slot_count':1,'frame_rate_hz':1000,'scan_time_utilization':1},'system':{'spad':{'channels_v':1},'acquisition':{'gate_width_ns':600000,'laser_shots':1,'period_ns':600000}},'electrical':{'dsp_time_us':700,'hist_copy_us':100,'bank_clear_us':0}})
    p=e['selected']['pipeline']
    assert p['feasible'] and not p['frame_ok'] and p['sustained_ok']
    assert p['tail_growth_ns']==pytest.approx(0)
    assert p['observed_output_frame_rate_hz']==pytest.approx(1000)


@pytest.mark.parametrize('field,value',[('buffer_bytes_per_link',0),('bank_bytes_per_chip',None)])
def test_manual_capacities_are_not_v6_inputs(field,value):
    with pytest.raises(ValueError):evaluate({'electrical':{field:value}})


def test_unknown_format_and_histogram_width_remain_unknown():
    _,e=evaluate({'transport':{'payload_format':'points','point_bytes':None}})
    assert not e['selected']['complete']
    _,e=evaluate({'transport':{'payload_format':'points','histogram_count_bits':None}})
    assert e['selected']['pipeline']['feasible'] is None
    assert e['selected']['memory']['maximum_bank_bytes'] is None


def test_work_limit_and_missing_default_are_errors():
    snapshot=copy.deepcopy(yaml_snapshot());snapshot['algorithms.yaml']['budget_pipeline_max_work']=1
    with frozen_yaml(snapshot),pytest.raises(ValueError,match='budget_pipeline_max_work'):evaluate({})
    snapshot=copy.deepcopy(yaml_snapshot());snapshot['defaults.yaml']['experiments']['budget_electrical'].pop('echo_max_bins')
    with frozen_yaml(snapshot),pytest.raises(ValueError):evaluate({})
    snapshot=copy.deepcopy(yaml_snapshot());snapshot['algorithms.yaml'].pop('budget_output_fifo_columns')
    with frozen_yaml(snapshot),pytest.raises(ValueError):evaluate({})


@pytest.mark.parametrize('value',[1e308,1e-320])
def test_finite_input_that_overflows_derived_mipi_is_rejected(value):
    with pytest.raises(ValueError,match='representable'):evaluate({'electrical':{'lane_rate_mbps':value}})


def test_large_echo_output_increases_automatic_bank_and_finite_fifo():
    _,e=evaluate({'transport':{'payload_format':'echo'},'electrical':{'echo_max_count':10000,'echo_max_bins':1000}})
    s=e['selected'];m=s['memory'];p=s['pipeline']
    assert m['maximum_bank_bytes']==max(s['result_bytes_per_chip'])
    assert m['maximum_bank_bytes']>max(s['raw_hist_bytes_per_chip'])
    assert p['feasible'] and p['fifo_slots']==Algorithms.load().budget_output_fifo_columns
    assert p['peak_fifo_bytes']<=p['fifo_capacity_bytes']


def test_192_lines_one_chip_four_lanes_exposes_hist_bank_demand():
    _,e=evaluate({'system':{'spad':{'channels_v':192},'readout':{'tdc_bin_ps':1000}},
                  'transport':{'payload_format':'points','point_bytes':50},'electrical':{'channels_per_chip':192,'data_lanes_per_link':4,'available_links':1}})
    assert e['chip_count']==e['link_count']==1
    assert e['total_data_lanes']==4 and e['total_raw_mbps']==6000
    p=e['selected']['pipeline']
    assert p['bank_required_bytes']==192*2048*2
    assert p['feasible'] and len(p['rows'])==3
    assert p['minimum_banks_total_bytes']==2*192*2048*2
    assert e['selected']['memory']['maximum_bank_bytes']==786432
    assert e['selected']['memory']['maximum_fifo_bytes']==2*(192*50+16)
    assert e['selected']['body_bytes_per_column']==192*50


def test_legacy_migration_preserves_point_size_and_removes_manual_capacities():
    from spad_lidar.webapi.budget import import_budget
    c=SimulationConfig.for_experiment('budget',{}).model_dump()
    c['transport'].update(point_bytes=8,enabled=False,buffer_count=2,dsp_time_us=None)
    c['electrical']['returns_per_point']=3;c['electrical']['buffer_bytes_per_link']=None
    migrated=import_budget(json.dumps(dict(schema_version=4,kind='hardware-budget',experiment=c)))
    assert migrated['transport']['point_bytes']==24
    assert 'returns_per_point' not in migrated['electrical'] and 'enabled' not in migrated['transport']
    assert 'buffer_bytes_per_link' not in migrated['electrical']
    assert 'bank_bytes_per_chip' not in migrated['electrical']
    assert migrated['geometry']==c['geometry']
    with pytest.raises(ValueError):SimulationConfig.for_experiment('budget',{'electrical':{'returns_per_point':3}})


def test_histogram_window_and_resolution_change_auto_memory():
    base={'system':{'spad':{'channels_v':192},'readout':{'tdc_bin_ps':1000}},'electrical':{'channels_per_chip':192}}
    _,full=evaluate(base)
    _,half=evaluate({**base,'system':{**base['system'],'acquisition':{'gate_width_ns':1024}}})
    _,fine=evaluate({**base,'system':{**base['system'],'readout':{'tdc_bin_ps':500}}})
    assert full['histogram']['gate_width_ns']==2048 and full['histogram']['bin_count']==2048
    assert half['histogram']['bin_count']==1024 and fine['histogram']['bin_count']==4096
    assert half['selected']['memory']['maximum_bank_bytes']*2==full['selected']['memory']['maximum_bank_bytes']
    assert fine['selected']['memory']['maximum_bank_bytes']==full['selected']['memory']['maximum_bank_bytes']*2
    _,single=evaluate({**base,'electrical':{**base['electrical'],'buffer_architecture':'single'}})
    assert single['selected']['memory']['total_sram_bytes']*2==full['selected']['memory']['total_sram_bytes']


def test_partial_chips_auto_memory_uses_actual_counts_and_fifo_is_finite():
    _,e=evaluate({'system':{'spad':{'channels_v':5}},'electrical':{'channels_per_chip':2,'chips_per_link':2,'lane_rate_mbps':1}})
    s=e['selected'];m=s['memory']
    assert m['total_sram_bytes']==sum(m['bank_bytes_per_chip'])*m['banks_per_chip']
    assert m['total_fifo_bytes']==sum(s['link_bytes_per_column'])*m['fifo_columns']
    for pipeline in s['pipeline_links']:
        assert pipeline['peak_fifo_bytes']<=pipeline['fifo_capacity_bytes']
    assert s['pipeline']['fifo_wait_max_ns']>0


def test_v5_import_discards_old_capacities_but_preserves_time_parameters():
    from spad_lidar.webapi.budget import import_budget
    c=SimulationConfig.for_experiment('budget',{'system':{'acquisition':{'gate_width_ns':1024},'readout':{'tdc_bin_ps':500}}}).model_dump()
    c['electrical'].update(bank_bytes_per_chip=65536,buffer_bytes_per_link=None)
    migrated=import_budget(json.dumps(dict(schema_version=5,kind='hardware-budget',experiment=c)))
    assert 'bank_bytes_per_chip' not in migrated['electrical'] and 'buffer_bytes_per_link' not in migrated['electrical']
    assert migrated['system']==c['system'] and migrated['targets']==c['targets']


@pytest.mark.parametrize('old',[float('nan'),-1,True,'65536'])
def test_obsolete_capacities_still_reject_invalid_legacy_input(old):
    from spad_lidar.legacy_config import migrate_budget_v6
    with pytest.raises(ValueError):migrate_budget_v6({'electrical':{'bank_bytes_per_chip':old}})


def test_copy_duration_controls_schedule_and_rate_changes_with_hist_data():
    base={'system':{'spad':{'channels_v':192},'readout':{'tdc_bin_ps':1000}},'electrical':{'channels_per_chip':192,'hist_copy_us':12}}
    _,e=evaluate(base);s=e['selected']
    assert s['pipeline']['copy_ns']==12000
    assert s['copy_required_mbps']==pytest.approx(192*2048*2*8/12)
    _,fine=evaluate({**base,'system':{**base['system'],'readout':{'tdc_bin_ps':500}}})
    assert fine['selected']['pipeline']['copy_ns']==12000
    assert fine['selected']['copy_required_mbps']==pytest.approx(2*s['copy_required_mbps'])
    _,single=evaluate({**base,'electrical':{**base['electrical'],'buffer_architecture':'single','hist_copy_us':None}})
    assert single['selected']['pipeline']['copy_ns']==0
    assert single['selected']['copy_required_mbps'] is None


@pytest.mark.parametrize('bad',[0,-1,float('nan'),float('inf'),True])
def test_invalid_copy_duration_rejected(bad):
    with pytest.raises(ValueError):evaluate({'electrical':{'hist_copy_us':bad}})


def test_tiny_copy_duration_rejects_unrepresentable_rate():
    with pytest.raises(ValueError,match='representable'):evaluate({'electrical':{'hist_copy_us':1e-320}})


def test_v6_rate_migrates_to_equivalent_worst_chip_duration():
    from spad_lidar.webapi.budget import import_budget
    cfg=SimulationConfig.for_experiment('budget',{'system':{'spad':{'channels_v':192},'readout':{'tdc_bin_ps':1000}},'electrical':{'channels_per_chip':192}}).model_dump()
    cfg['electrical'].pop('hist_copy_us');cfg['electrical']['hist_copy_mbps']=1000000
    migrated=import_budget(json.dumps(dict(schema_version=6,kind='hardware-budget',experiment=cfg)))
    assert 'hist_copy_mbps' not in migrated['electrical']
    assert migrated['electrical']['hist_copy_us']==pytest.approx(6.291456)
    assert migrated['system']==cfg['system'] and migrated['targets']==cfg['targets']
    _,e=evaluate(migrated)
    assert e['selected']['copy_required_mbps']==pytest.approx(1000000)


def test_dphy_breakdown_matches_actual_slot_service_including_frame_packets():
    _,e=evaluate({'system':{'spad':{'channels_v':192},'readout':{'tdc_bin_ps':1000}},'targets':{'slot_count':1},'transport':{'payload_format':'points','point_bytes':16},'electrical':{'channels_per_chip':192,'data_lanes_per_link':4,'payload_efficiency':.8,'lane_rate_mbps':1500,'chip_header_bytes':16,'packet_payload_bytes':4096,'burst_gap_us':2}})
    t=e['selected']['transmission']
    assert t['payload_bytes']==3088 and t['protocol_bytes']==6 and t['wire_bytes']==3094
    assert t['effective_rate_mbps']==4800
    assert t['serial_time_ns']/1000==pytest.approx(5.156666666666666)
    assert t['gap_time_ns']==2000
    assert t['base_time_ns']==pytest.approx(t['serial_time_ns']+t['gap_time_ns'])
    assert t['slot_send_times'][0]['duration_ns']==pytest.approx(t['base_time_ns']+2*t['frame_short_time_ns_each'])

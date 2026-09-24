"""Finite column buffers, DSP service and FIFO MIPI output on one absolute clock."""
import math


def transport_plan(cfg,columns,*,record_counts=None):
    t=cfg.transport
    assumptions=['Buffers are reserved at column acquisition start and released at MIPI completion.',
        'All configured H/V readout channels belong to one column; row processing is parallel.',
        'MIPI is after DSP, FIFO, with one output link. Input scan times are never delayed to hide overload.',
        'Dropped columns retain offline detector records for audit; they do not become delivered output.']
    if not t.enabled:return {'status':'not_configured','rows':[],'assumptions':assumptions,'note':'DSP/MIPI尚未配置。请启用并填写耗时或数据格式，未知值不按零计算。'}
    if t.mipi_mode=='payload' and t.payload_format=='events' and record_counts is None:
        return {'status':'needs_acquisition','rows':[],'assumptions':assumptions,'note':'原始事件量需取实际记录；完整计划的事件数据未齐备，局部实验不能推算整帧搬运量。'}
    channels=cfg.spad.channels_h*cfg.spad.channels_v
    histogram_bins=math.ceil(cfg.acquisition.gate_width_ns/(cfg.readout.tdc_bin_ps*1e-3))
    dsp_duration=t.dsp_time_us*1000
    initiation=dsp_duration if t.dsp_mode=='serial' else t.dsp_initiation_us*1000
    buffers=[-math.inf]*t.buffer_count;next_dsp=-math.inf;next_mipi=-math.inf
    rows=[];total_bytes=0;total_mipi_ns=0.;drops=0
    for c in columns:
        free=[i for i,end in enumerate(buffers) if end<=c['start_ns']]
        if not free:
            if t.overflow_policy=='error':raise ValueError(f'Column {c["column_id"]}: no free output buffer at acquisition start')
            drops+=1;rows.append({'column_id':c['column_id'],'frame':c['frame'],'column':c['column'],
                'status':'dropped_no_buffer','acquisition_start_ns':c['start_ns'],'data_ready_ns':c['data_ready_ns']})
            continue
        buffer_id=free[0]
        if t.mipi_mode=='payload':
            if t.payload_format=='points':payload=channels*t.point_bytes
            elif t.payload_format=='histogram':payload=math.ceil(channels*histogram_bins*t.histogram_count_bits/8)
            else:payload=record_counts.get(c['column_id'],0)*t.event_record_bytes
            byte_count=t.column_header_bytes+payload
            mipi_duration=byte_count*8/(t.mipi_net_mbps*1e6)*1e9
            total_bytes+=byte_count
        else:byte_count=None;mipi_duration=t.mipi_time_us*1000
        if not math.isfinite(dsp_duration) or not math.isfinite(initiation) or not math.isfinite(mipi_duration):raise ValueError('DSP/MIPI derived duration is not finite')
        ds=max(c['data_ready_ns'],next_dsp);de=ds+dsp_duration;next_dsp=ds+initiation
        ms=max(de,next_mipi);me=ms+mipi_duration;next_mipi=me;buffers[buffer_id]=me;total_mipi_ns+=mipi_duration
        if not math.isfinite(me):raise ValueError('DSP/MIPI completion time is not finite')
        rows.append({'column_id':c['column_id'],'frame':c['frame'],'column':c['column'],'status':'scheduled',
            'buffer_id':buffer_id,'acquisition_start_ns':c['start_ns'],'data_ready_ns':c['data_ready_ns'],
            'dsp_start_ns':ds,'dsp_end_ns':de,'mipi_start_ns':ms,'mipi_end_ns':me,
            'dsp_wait_ns':ds-c['data_ready_ns'],'mipi_wait_ns':ms-de,'output_latency_ns':me-c['start_ns'],
            'column_bytes':byte_count})
    events=[]
    for row in rows:
        if row['status']=='scheduled':events.extend([(row['acquisition_start_ns'],1),(row['mipi_end_ns'],-1)])
    occupied=peak=0
    for _,delta in sorted(events):occupied+=delta;peak=max(peak,occupied)
    duration=cfg.budget['frame_period_ns']*cfg.acquisition.frame_count
    completed=[r for r in rows if r['status']=='scheduled']
    return {'status':'overloaded' if drops else 'scheduled','rows':rows,'assumptions':assumptions,
        'summary':{'input_columns':len(columns),'delivered_columns':len(completed),'dropped_columns':drops,
            'peak_occupied_buffers':peak,'last_output_ns':max((r['mipi_end_ns'] for r in completed),default=None),
            'outputs_after_observation':sum(r['mipi_end_ns']>duration for r in completed),
            'max_latency_ns':max((r['output_latency_ns'] for r in completed),default=None),
            'total_column_bytes':total_bytes if t.mipi_mode=='payload' else None,
            'average_payload_mbps':total_bytes*8/(duration*1e-9)/1e6 if t.mipi_mode=='payload' else None,
            'mipi_service_ns':total_mipi_ns,'observation_ns':duration},
        'note':'按给定服务时间排程，不代表实测硬件性能。净载荷速率和列头需显式提供；直方图模式预算位宽，不执行截断/饱和编码。'}

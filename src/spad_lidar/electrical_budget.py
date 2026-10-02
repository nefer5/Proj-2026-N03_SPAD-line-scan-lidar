"""SPAD payload, explicit CSI-2 overhead and shared finite-resource timing."""
import math
from .budget_pipeline import schedule_link,required_copy_rate_mbps


def packet_budget(payload_bytes,maximum_payload_bytes):
    """Classic CSI-2 long packet: 4-byte header, WC payload, 2-byte CRC."""
    count=(payload_bytes+maximum_payload_bytes-1)//maximum_payload_bytes
    return dict(payload_bytes=payload_bytes,long_packets=count,
                long_packet_overhead_bytes=6*count,wire_bytes=payload_bytes+6*count,
                last_payload_bytes=payload_bytes-(count-1)*maximum_payload_bytes if count else 0)


def histogram_storage(cfg,fmt):
    """Common storage sizing, also used by explicit legacy-rate migration."""
    e=cfg.electrical;t=cfg.transport
    channels=cfg.system.spad.channels_h*cfg.system.spad.channels_v
    counts=[min(e.channels_per_chip,channels-i) for i in range(0,channels,e.channels_per_chip)]
    bins=math.ceil(cfg.system.acquisition.gate_width_ns*1000/cfg.system.readout.tdc_bin_ps)
    exposures=cfg.system.acquisition.laser_shots if fmt=='histogram' and e.histogram_mode=='per_shot' else 1
    sizes=[None if t.histogram_count_bits is None else ((count*bins*t.histogram_count_bits+7)//8)*exposures for count in counts]
    return dict(channel_counts=counts,bin_count=bins,exposures=exposures,bytes_per_chip=sizes)


def electrical_budget(cfg,timing,envelope_ns,algorithms):
    e=cfg.electrical;t=cfg.transport
    storage=histogram_storage(cfg,t.payload_format)
    counts=storage['channel_counts'];bins=storage['bin_count']
    chips=len(counts);links=math.ceil(chips/e.chips_per_link)
    net=None
    if e.capacity_mode=='lanes':
        if e.lane_rate_mbps is not None and e.payload_efficiency is not None:
            net=e.lane_rate_mbps*e.data_lanes_per_link*e.payload_efficiency
    elif t.mipi_net_mbps is not None:net=t.mipi_net_mbps/links
    if net is not None and (not math.isfinite(net) or net<=0 or not math.isfinite(net*links)):
        raise ValueError('MIPI service rate is not representable; check lane rate and link count')
    groups=[counts[i:i+e.chips_per_link] for i in range(0,chips,e.chips_per_link)]
    variants=len({tuple(c) for c in groups})
    work=3*variants*cfg.targets.slot_count*algorithms.budget_pipeline_frames
    if work>algorithms.budget_pipeline_max_work:raise ValueError('Pipeline scheduling work exceeds budget_pipeline_max_work')
    formats={}
    for fmt in ('histogram','points','echo'):
        raw=histogram_storage(cfg,fmt)['bytes_per_chip']
        sizes=[]
        for count,hist in zip(counts,raw):
            if fmt=='histogram':body=hist
            elif fmt=='points':body=None if t.point_bytes is None else count*t.point_bytes
            else:body=None if t.histogram_count_bits is None else count*e.echo_max_count*(e.echo_descriptor_bytes+(e.echo_max_bins*t.histogram_count_bits+7)//8)
            sizes.append(None if body is None else body+e.chip_header_bytes)
        if any(v is None for v in sizes) or t.column_header_bytes is None:
            formats[fmt]=dict(complete=False,note='该输出格式的记录长度、计数字宽或应用头长度未指定。',timeline=[])
            continue
        payloads=[];wires=[];packets=[]
        # Per-link metadata is included in the first chip payload once per slot.
        for first in range(0,chips,e.chips_per_link):
            part=sizes[first:first+e.chips_per_link]
            ps=[packet_budget(v+(t.column_header_bytes if j==0 else 0),e.packet_payload_bytes) for j,v in enumerate(part)]
            payloads.append(sum(part)+t.column_header_bytes)
            packets.append(sum(p['long_packets'] for p in ps))
            wires.append(sum(p['wire_bytes'] for p in ps)+(8 if e.line_short_packets else 0))
        total=sum(payloads);n=cfg.targets.slot_count
        frame_payload=total*n
        # FS+FE are mandatory short packets, each 4B per link per logical frame.
        frame_wire=sum(wires)*n+8*links
        wire_times=[None if net is None else w*8/net*1000+p*e.burst_gap_us*1000 for w,p in zip(wires,packets)]
        if any(v is not None and (not math.isfinite(v) or v<=0) for v in wire_times):
            raise ValueError('MIPI transmission time is not representable; check payload and line rate')
        pipelines=[];cache={}
        for index,group in enumerate(groups):
            signature=tuple(group)
            if signature not in cache:
                data=cfg.model_copy(update={'transport':t.model_copy(update={'payload_format':fmt})})
                bank=raw[index*e.chips_per_link]
                result_bank=sizes[index*e.chips_per_link]-e.chip_header_bytes
                cache[signature]=schedule_link(data,timing,envelope_ns,bank,result_bank,payloads[index],wire_times[index],net,algorithms)
            pipelines.append(cache[signature])
        worst=max(range(links),key=lambda i: (not bool(pipelines[i].get('feasible')),pipelines[i].get('frame_completion_ns',0),wires[i]))
        pipe=pipelines[worst]
        avg=frame_wire*8*cfg.targets.frame_rate_hz/1e6
        demand=[(w*n+8)*8*cfg.targets.frame_rate_hz/1e6 for w in wires]
        known=net is not None
        # Explicit burst gaps consume link time in addition to byte transmission.
        average_ok=None if not known else all((wire_times[i]*n+8*8/net*1000)<=timing['frame_period_ns'] for i in range(links))
        all_feasible=all(p.get('feasible') for p in pipelines)
        schedules=[p for p in pipelines if p.get('feasible')]
        result_sizes=[v-e.chip_header_bytes for v in sizes]
        banks=2 if e.buffer_architecture=='fixed_ab' else 1
        bank_sizes=[None if v is None else max(v,r) for v,r in zip(raw,result_sizes)]
        sram_total=None if any(v is None for v in bank_sizes) else sum(bank_sizes)*banks
        fifo_sizes=[v*algorithms.budget_output_fifo_columns for v in payloads]
        memory=dict(mode='automatic_budget',banks_per_chip=banks,bank_bytes_per_chip=bank_sizes,
            maximum_bank_bytes=None if sram_total is None else max(bank_sizes),
            maximum_chip_sram_bytes=None if sram_total is None else max(bank_sizes)*banks,total_sram_bytes=sram_total,
            fifo_columns=algorithms.budget_output_fifo_columns,fifo_bytes_per_link=fifo_sizes,
            maximum_fifo_bytes=max(fifo_sizes),total_fifo_bytes=sum(fifo_sizes),
            total_memory_bytes=None if sram_total is None else sram_total+sum(fifo_sizes),
            note='逻辑存储需求自动计算，B结果按原位覆盖Hist；不含DSP工作区、SRAM对齐/ECC。FIFO有限，按整列块保留至TX结束。不是实装容量验证。')
        rates=[None if e.buffer_architecture=='single' else required_copy_rate_mbps(v,e.hist_copy_us) for v in raw]
        transmission=dict(link_index=worst,payload_bytes=payloads[worst],long_packets=packets[worst],
            protocol_bytes=wires[worst]-payloads[worst],
            lane_count=e.data_lanes_per_link,lane_rate_mbps=e.lane_rate_mbps,
            physical_utilization=e.payload_efficiency,capacity_mode=e.capacity_mode,
            long_packet_overhead_bytes=packets[worst]*6,line_short_packet_bytes=8 if e.line_short_packets else 0,
            wire_bytes=wires[worst],effective_rate_mbps=net,
            serial_time_ns=None if net is None else wires[worst]*8/net*1000,
            gap_time_ns=packets[worst]*e.burst_gap_us*1000,base_time_ns=wire_times[worst],
            frame_short_packet_bytes_each=4,frame_short_time_ns_each=None if net is None else 4*8/net*1000,
            slot_send_times=[dict(column=row['column'],start_ns=row['start_ns'],end_ns=row['end_ns'],
                                  duration_ns=row['end_ns']-row['start_ns']) for row in pipe.get('rows',[])])
        formats[fmt]=dict(complete=True,chip_bytes_per_column=sizes,link_bytes_per_column=payloads,
            transmission=transmission,copy_required_mbps_per_chip=rates,
            copy_required_mbps=None if any(v is None for v in rates) else max(rates),
            link_wire_bytes_per_column=wires,link_packets_per_column=packets,
            raw_hist_bytes_per_chip=raw,result_bytes_per_chip=[v-e.chip_header_bytes for v in sizes],body_bytes_per_column=sum(sizes)-chips*e.chip_header_bytes,
            header_bytes_per_column=chips*e.chip_header_bytes+links*t.column_header_bytes,
            total_bytes_per_column=total,bytes_per_frame=frame_payload,wire_bytes_per_frame=frame_wire,
            csi_overhead_bytes_per_frame=frame_wire-frame_payload,
            total_required_mbps=avg,payload_required_mbps=frame_payload*8*cfg.targets.frame_rate_hz/1e6,
            worst_link_required_mbps=max(demand),worst_link_scan_mbps=max(wires)*8/timing['slot_max_ns']*1000,
            wire_ns=wire_times[worst],ready_ns=pipe['rows'][0]['ready_ns'] if pipe.get('rows') else None,
            frame_completion_ns=max(p['frame_completion_ns'] for p in schedules) if all_feasible else None,
            peak_buffer_bytes_per_link=max(p['peak_fifo_bytes'] for p in schedules) if all_feasible else None,
            max_frame_rate_hz=min(p['resource_frame_rate_bound_hz'] for p in schedules) if all_feasible else None,
            average_bandwidth_ok=average_ok,no_backlog=None if not known else max(wire_times)<=timing['slot_max_ns'],
            frame_ok=all(p['frame_ok'] for p in schedules) if all_feasible else None,
            memory=memory,
            pipeline=pipe,pipeline_links=pipelines,timeline=pipe.get('timeline',[]),worst_link_index=worst,
            note='Echo按最大回波数×最大bin窗做上限预算，不强制实际填充。' if fmt=='echo' else '')
    selected=formats[t.payload_format]
    return dict(format=t.payload_format,formats=formats,selected=selected,chip_count=chips,link_count=links,
        channel_counts_per_chip=counts,total_data_lanes=links*e.data_lanes_per_link,net_mbps_per_link=net,
        total_net_mbps=None if net is None else net*links,
        total_raw_mbps=None if e.capacity_mode!='lanes' or e.lane_rate_mbps is None else e.lane_rate_mbps*e.data_lanes_per_link*links,
        ports_ok=None if e.available_links is None else links<=e.available_links,
        scheduler_work=work,protocol='CSI-2 / D-PHY',fifo_model='whole_link_column_until_tx_complete',
        histogram=dict(gate_start_ns=cfg.system.acquisition.gate_start_ns,gate_width_ns=cfg.system.acquisition.gate_width_ns,
                       bin_width_ps=cfg.system.readout.tdc_bin_ps,bin_width_ns=cfg.system.readout.tdc_bin_ps/1000,bin_count=bins),
        note='片内Hist、片内非流水DSP；全Hist旁路DSP。各芯片搬移/DSP并行，同链路整列同步交接，采用最慢芯片。'
             'SRAM容量自动按Hist与结果较大者预算，未计DSP额外工作区。FIFO自动按算法策略预留有限列块，满时背压B再到A；这些是资源预算，非实装容量验证。Range字节数为一个完整点，不再乘回波数。'
             'CSI-2每长包4B头+2B CRC，FS/FE各4B/链路/帧；应用头在payload内，物理利用率不含这些显式开销。'
             'burst间隔逐长包另计。lane输入为比特率，clock不承载payload，不再乘DDR。'
             '多个chip汇聚需要桥接器。每link按顺序应用流预算，chip身份由应用元数据约定，不模拟VC仲裁；接收端自定义类型/包长尚未验证。'
             '资源调度保留连续多帧状态；资源上限是必要上界，有限帧观察不是长期稳定证明。'
             '延后slot未重新计算镜面角位移、光子数、PRBS或光功率，不能据此自动改变扫描工况。')

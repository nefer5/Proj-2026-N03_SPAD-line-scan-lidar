"""Declared SPAD payload -> MIPI service, with ideal per-column FIFO scheduling."""
import math


def electrical_budget(cfg,timing,envelope_ns):
    e=cfg.electrical;t=cfg.transport
    channels=cfg.system.spad.channels_h*cfg.system.spad.channels_v
    chips=math.ceil(channels/e.channels_per_chip)
    links=math.ceil(chips/e.chips_per_link)
    bins=math.ceil(cfg.system.acquisition.gate_width_ns*1000/cfg.system.readout.tdc_bin_ps)
    exposures=cfg.system.acquisition.laser_shots if e.histogram_mode=='per_shot' else 1
    net=None
    if e.capacity_mode=='lanes':
        if e.lane_rate_mbps is not None and e.payload_efficiency is not None:
            net=e.lane_rate_mbps*e.data_lanes_per_link*e.payload_efficiency
    elif t.mipi_net_mbps is not None:net=t.mipi_net_mbps/links
    ready=None if e.ready_delay_us is None else envelope_ns+e.ready_delay_us*1000
    formats={}
    for fmt in ['histogram','points']:
        sizes=[]
        for chip in range(chips):
            count=min(e.channels_per_chip,channels-chip*e.channels_per_chip)
            body=None
            if fmt=='histogram' and t.histogram_count_bits is not None:
                body=math.ceil(count*bins*t.histogram_count_bits/8)*exposures
            if fmt=='points' and t.point_bytes is not None:body=count*e.returns_per_point*t.point_bytes
            sizes.append(None if body is None else body+e.chip_header_bytes)
        if any(v is None for v in sizes):formats[fmt]={'complete':False,'note':'需指定该格式字宽/记录长度及每芯片每列头部字节。'};continue
        link_sizes=[sum(sizes[i:i+e.chips_per_link]) for i in range(0,chips,e.chips_per_link)]
        worst=max(link_sizes);total=sum(sizes);frame=total*cfg.targets.slot_count
        avg=frame*8*cfg.targets.frame_rate_hz/1e6
        wire=None if net is None else worst*8/net*1000
        end=None if ready is None or wire is None else ready+(cfg.targets.slot_count-1)*max(timing['slot_max_ns'],wire)+wire
        peak_buffer=None if net is None else math.ceil(max(worst,worst*cfg.targets.slot_count-net/8000*(cfg.targets.slot_count-1)*timing['slot_max_ns']))
        max_fps=None if wire is None or ready is None else min(
            1e9/(ready+cfg.targets.slot_count*wire),
            (1-cfg.targets.scan_time_utilization*(cfg.targets.slot_count-1)/cfg.targets.slot_count)*1e9/(ready+wire))
        timeline=[] if wire is None or ready is None else [{'column':i,'ready_ns':ready+i*timing['slot_max_ns'],
            'start_ns':ready+i*max(timing['slot_max_ns'],wire),'end_ns':ready+i*max(timing['slot_max_ns'],wire)+wire}
            for i in timing['frame_preview_indices']]
        formats[fmt]={'complete':True,'chip_bytes_per_column':sizes,'link_bytes_per_column':link_sizes,
            'body_bytes_per_column':total-chips*e.chip_header_bytes,'header_bytes_per_column':chips*e.chip_header_bytes,'total_bytes_per_column':total,'bytes_per_frame':frame,'total_required_mbps':avg,
            'worst_link_required_mbps':worst*cfg.targets.slot_count*8*cfg.targets.frame_rate_hz/1e6,
            'worst_link_scan_mbps':worst*8/timing['slot_max_ns']*1000,
            'wire_ns':wire,'ready_ns':ready,'frame_completion_ns':end,'peak_buffer_bytes_per_link':peak_buffer,
            'max_frame_rate_hz':max_fps,'average_bandwidth_ok':None if net is None else avg<=net*links,
            'no_backlog':None if wire is None else wire<=timing['slot_max_ns'],
            'frame_ok':None if end is None else end<=timing['frame_period_ns'],
            'buffer_ok':None if e.buffer_bytes_per_link is None or peak_buffer is None else peak_buffer<=e.buffer_bytes_per_link,
            'timeline':timeline}
    selected=formats.get(t.payload_format,{'complete':False,'note':'系统预算目前支持直方图或range记录。'})
    return {'format':t.payload_format,'formats':formats,'selected':selected,'chip_count':chips,'link_count':links,
        'total_data_lanes':links*e.data_lanes_per_link,'net_mbps_per_link':net,
        'total_net_mbps':None if net is None else net*links,
        'total_raw_mbps':None if e.capacity_mode!='lanes' or e.lane_rate_mbps is None else e.lane_rate_mbps*e.data_lanes_per_link*links,
        'ports_ok':None if e.available_links is None else links<=e.available_links,
        'note':'SPAD输出，不含SPI接口。每chip按整列就绪发包；直方图可选列内累计或逐发输出，range为声明的固定记录，不模拟range算法。MIPI lane输入为比特率，不是时钟频率；效率含协议/切换空隙，不重复扣用户包头。汇聚多个chip需实际桥接，不能直接并联发送器。缓存峰值含正在发送包，未知容量不判通过。'}

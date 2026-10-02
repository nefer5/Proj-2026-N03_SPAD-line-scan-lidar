"""Deterministic fixed-role SRAM scheduling, with finite whole-column output FIFO.

One link receives a synchronized column from its chips. Chip copies/DSP operate
in parallel; the slowest chip controls the link handoff. The link reserves its
complete column block until TX completion. No event loss or unlimited queue.
"""
import heapq
import math


def required_copy_rate_mbps(byte_count,duration_us):
    if byte_count is None or duration_us is None:return None
    rate=byte_count*8/duration_us
    if not math.isfinite(rate):raise ValueError('Required Hist copy rate is not representable')
    return rate


def schedule_link(cfg,timing,envelope_ns,raw_bank_bytes,result_bank_bytes,block_bytes,wire_ns,net_mbps,algorithms):
    e=cfg.electrical
    missing=[]
    for key in ('bank_clear_us','ready_delay_us','mipi_pack_us'):
        if getattr(e,key) is None:missing.append(key)
    if e.buffer_architecture=='fixed_ab' and e.hist_copy_us is None:missing.append('hist_copy_us')
    bypass=cfg.transport.payload_format=='histogram'
    if not bypass and e.dsp_time_us is None:missing.append('dsp_time_us')
    if raw_bank_bytes is None:missing.append('histogram_count_bits')
    if net_mbps is None:missing.append('MIPI capacity')
    if missing:return {'complete':False,'feasible':None,'note':'时序缺少：'+', '.join(missing),'rows':[]}
    bank_required=max(raw_bank_bytes,result_bank_bytes)
    banks=2 if e.buffer_architecture=='fixed_ab' else 1
    fifo_capacity=block_bytes*algorithms.budget_output_fifo_columns
    slots=cfg.targets.slot_count
    period=timing['frame_period_ns'];slot=timing['slot_max_ns']
    capture=max(envelope_ns,slot) if e.handoff_policy=='slot_end' else envelope_ns
    copy=e.hist_copy_us*1000 if e.buffer_architecture=='fixed_ab' else 0
    copy_rate=required_copy_rate_mbps(raw_bank_bytes,e.hist_copy_us) if e.buffer_architecture=='fixed_ab' else None
    clear=e.bank_clear_us*1000;delay=e.ready_delay_us*1000
    dsp=0 if bypass else e.dsp_time_us*1000;pack=e.mipi_pack_us*1000
    if not all(math.isfinite(v) for v in (capture,copy,clear,delay,dsp,pack,period,slot)):
        raise ValueError('Pipeline stage time is not representable; check resource rates and frame timing')
    capacity=algorithms.budget_output_fifo_columns
    a_free=b_free=copy_free=pack_free=wire_free=0.
    live=[];rows=[];summaries=[];sampled=[];peak=0;wait_max=delay_max=0.
    # FS/FE are 4-byte short packets each; keep them in actual link service.
    short=4*8/net_mbps*1000
    for frame in range(algorithms.budget_pipeline_frames):
        first_capture=scan_end=last_tx=frame_delay=0.
        for column in range(slots):
            planned=frame*period+column*slot
            start=max(planned,a_free)
            cap_end=start+envelope_ns;ready=start+capture
            if column==0:first_capture=start
            scan_end=max(scan_end,cap_end)
            copy_start=max(ready,b_free,copy_free) if e.buffer_architecture=='fixed_ab' else ready
            copy_end=copy_start+copy;copy_free=copy_end
            input_end=copy_end+delay;dsp_end=input_end+dsp
            commit=dsp_end
            while True:
                while live and live[0]<=commit:heapq.heappop(live)
                if len(live)<capacity:break
                commit=live[0]
            pack_start=max(commit,pack_free);pack_end=pack_start+pack;pack_free=pack_end
            send_start=max(pack_end,wire_free)
            send_end=send_start+wire_ns+(short if column==0 else 0)+(short if column==slots-1 else 0)
            wire_free=send_end;heapq.heappush(live,send_end)
            peak=max(peak,len(live)*block_bytes)
            if e.buffer_architecture=='fixed_ab':
                b_free=commit;clear_start=copy_end
            else:
                b_free=commit;clear_start=commit
            clear_end=clear_start+clear;a_free=clear_end
            wait=commit-dsp_end;late=start-planned
            wait_max=max(wait_max,wait);delay_max=max(delay_max,late);frame_delay=max(frame_delay,late)
            row=dict(frame=frame,column=column,planned_ns=planned,capture_start_ns=start,
                capture_end_ns=cap_end,hist_ready_ns=ready,copy_start_ns=copy_start,copy_end_ns=copy_end,
                clear_start_ns=clear_start,clear_end_ns=clear_end,input_start_ns=copy_end,input_end_ns=input_end,
                dsp_start_ns=input_end,dsp_end_ns=dsp_end,commit_ns=commit,
                pack_start_ns=pack_start,pack_end_ns=pack_end,start_ns=send_start,end_ns=send_end,
                fifo_start_ns=commit,fifo_end_ns=send_end,fifo_bytes=block_bytes,
                delay_ns=late,fifo_wait_ns=wait,ready_ns=dsp_end)
            if frame==0 and column<algorithms.budget_pipeline_preview_slots:rows.append(row)
            if frame==0 and column in timing['frame_preview_indices']:sampled.append(row)
            last_tx=send_end
        summaries.append(dict(frame=frame,first_capture_ns=first_capture,scan_end_ns=scan_end,
            completion_ns=last_tx,tail_ns=max(0,last_tx-(frame+1)*period),max_slot_delay_ns=frame_delay,
            scan_ok=scan_end<=frame*period+timing['scan_allocatable_ns']))
    # Pure floating-point roundoff allowance; this is not an engineering tolerance.
    eps=math.ulp(max(period,wire_free))*8
    tail_growth=max(0,summaries[-1]['tail_ns']-summaries[-2]['tail_ns'])
    cadence_ok=delay_max<=eps
    cycle=1e9/(summaries[-1]['completion_ns']-summaries[-2]['completion_ns'])
    # Resource bound, not a search/claim of an exactly attainable maximum FPS.
    front=capture+copy+clear if e.buffer_architecture=='fixed_ab' else capture+delay+dsp+clear
    processing=copy+delay+dsp if e.buffer_architecture=='fixed_ab' else front
    scan_bound=cfg.targets.scan_time_utilization*1e9/(slots*max(front,processing))
    service=max(pack,wire_ns) if capacity>=2 else pack+wire_ns
    wire_bound=1e9/(slots*service+2*short)
    return dict(complete=True,feasible=True,rows=rows,timeline=sampled,frames=summaries,
        acquisition_ns=capture,copy_ns=copy,
        copy_required_mbps=copy_rate,
        clear_ns=clear,input_delay_ns=delay,dsp_ns=dsp,pack_ns=pack,
        bank_required_bytes=bank_required,minimum_banks_total_bytes=bank_required*banks,bank_count=banks,
        raw_hist_bytes=raw_bank_bytes,result_bank_bytes=result_bank_bytes,
        fifo_capacity_bytes=fifo_capacity,fifo_minimum_bytes=block_bytes,fifo_slots=capacity,peak_fifo_bytes=peak,
        fifo_wait_max_ns=wait_max,max_slot_delay_ns=delay_max,tail_growth_ns=tail_growth,
        frame_completion_ns=summaries[0]['completion_ns'],frame_ok=summaries[0]['completion_ns']<=period+eps,
        scan_ok=all(s['scan_ok'] for s in summaries),cadence_ok=cadence_ok,
        sustained_ok=cadence_ok and tail_growth<=eps,observed_output_frame_rate_hz=cycle,
        resource_frame_rate_bound_hz=min(scan_bound,wire_bound),
        dsp_bypassed=bypass,architecture=e.buffer_architecture,
        note='固定A采集/B处理；B在整列结果入输出FIFO后释放。' if e.buffer_architecture=='fixed_ab' else '单块SRAM在结果入输出FIFO、清零后才可采下一slot。')

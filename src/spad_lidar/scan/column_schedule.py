"""Explicit column and trigger clocks; gate unions do not duplicate exposure."""
import bisect
from dataclasses import replace
import numpy as np
from ..contracts import AcquisitionWindow
from ..spad.readout.gates import FragmentAwareReadout
from ..timing.gates import GatedProgram,merge_intervals
from .trajectory import mirror_pose


def scheduled_energy(cfg,schedule,end_ns,*,start_ns=0):
    from ..numerics.temporal import temporal_cdf
    emitted=[r for r in schedule if r['emitted']]
    centers=np.array([r['emission_time_ns'] for r in emitted]);input_energy=np.array([r['energy_nj'] for r in emitted])*1e-9
    tail=None if cfg.exposure.tail_fraction==0 else (cfg.exposure.tail_fraction,cfg.exposure.tail_tau_ns)
    fractions=temporal_cdf(end_ns-centers,cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,tail)-temporal_cdf(start_ns-centers,cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,tail)
    incident=float(fractions@input_energy)
    return {'input_energy_of_measured_sources_j':sum(r['energy_nj']*1e-9 for r in emitted if r['measured']),
        'center_accounted_tx_output_energy_j':sum(r['energy_nj']*1e-9*cfg.tx.tx_efficiency for r in emitted if start_ns<=r['emission_time_ns']<end_ns),
        'tx_input_energy_in_observation_j':incident,'tx_output_energy_in_observation_j':incident*cfg.tx.tx_efficiency,
        'tx_input_average_power_w':incident/((end_ns-start_ns)*1e-9),'tx_average_power_w':incident*cfg.tx.tx_efficiency/((end_ns-start_ns)*1e-9)}


def acquisition_scope(cfg,a,program,rows,columns,budget):
    """Explicit local experiment, not a silently cropped full-frame result.

    Only selected source columns and a configured finite predecessor warmup are
    simulated. Future/outside columns are not excited. Photon seeds are local to
    this experimental scope; this is not deterministic replay of a full frame.
    """
    if cfg.acquisition.scope_mode=='frame':
        return program,rows,columns,{**budget,'observation_start_ns':0.,'observation_end_ns':budget['duration_ns'],
            'observation_duration_ns':budget['duration_ns'],'measured_column_count':len(columns),'scope_mode':'frame'}
    lo=cfg.acquisition.scope_first_column;hi=lo+cfg.acquisition.scope_column_count
    selected=columns[lo:hi];start=selected[0]['start_ns'];end=selected[-1]['end_ns']
    first=next(i for i,r in enumerate(rows) if r['column_id']==lo)
    stop=max(i for i,r in enumerate(rows) if lo<=r['column_id']<hi)+1
    begin=max(0,first-a.readout_warmup_cycles);windows=[];segments={};source=[]
    for i in range(begin,stop):
        old=program.windows[i];finish=min(old.end_ns,end);pieces=[(l,min(h,end)) for l,h in program.detector_intervals(old) if l<end]
        open_ns=pieces[0][0] if pieces else old.start_ns;close_ns=pieces[-1][1] if pieces else old.start_ns
        measured=i>=first
        windows.append(replace(old,end_ns=finish,measured=measured,gate_open_ns=open_ns,gate_close_ns=close_ns,
                               detector_gate_open_ns=open_ns,detector_gate_close_ns=close_ns))
        segments[old.cycle]=pieces;source.append({**rows[i],'measured':measured,'end_ns':finish,'gate_segments_ns':pieces})
    scoped={**budget,'observation_start_ns':start,'observation_end_ns':end,'observation_duration_ns':end-start,
        'measured_column_count':len(selected),'scope_mode':'columns',
        'scope_note':'Local experiment: only selected source columns and finite predecessor warmup are excited; unsimulated columns are unknown, not zero. This is not replay/cropping of a full-frame random realization.',
        'trigger_count':sum(r['measured'] and r['has_pulse'] for r in source),
        'emission_count':sum(r['measured'] and r['emitted'] for r in source),
        'gate_union_exposure_ns':sum(h-l for w in windows if w.measured for l,h in segments[w.cycle]),
        'incomplete_recording_columns':[c['column_id'] for c in selected if c['data_ready_ns']>end]}
    return GatedProgram(windows,segments),source,selected,scoped


def build_column_schedule(cfg,a):
    b=cfg.budget;frame_ns=b['frame_period_ns'];slot_ns=b['slot_target_ns'];n=cfg.system_targets.slot_count
    total_ns=frame_ns*cfg.acquisition.frame_count
    if not np.isfinite(total_ns) or np.spacing(total_ns)>=min(cfg.readout.tdc_bin_ps,cfg.tx.pulse_fwhm_ps)*1e-3:
        raise ValueError('Column clock cannot resolve pulse/TDC precision over the requested observation')
    columns=[];raw=[]
    for f in range(cfg.acquisition.frame_count):
        for col in range(n):
            start=f*frame_ns+col*slot_ns;end=f*frame_ns+(col+1)*slot_ns
            column={'column_id':f*n+col,'frame':f,'column':col,'start_ns':start,'end_ns':end}
            columns.append(column)
            for pidx,p in enumerate(cfg.exposure.pulses):
                raw.append({'nominal_time_ns':start+p.time_offset_ns,'column_id':column['column_id'],
                    'frame':f,'column':col,'pulse_index':pidx,
                    'energy_nj':cfg.tx.total_pulse_energy_nj if p.energy_nj is None else p.energy_nj,'has_pulse':True})
            # Dark/empty columns still own a time interval, permitting column gating.
            if not cfg.exposure.pulses or cfg.exposure.pulses[0].time_offset_ns>0:
                raw.append({'nominal_time_ns':start,'column_id':column['column_id'],'frame':f,'column':col,
                            'pulse_index':None,'energy_nj':0.,'has_pulse':False})
    raw.sort(key=lambda r:r['nominal_time_ns'])
    if not raw:raise ValueError('Column program has no intervals')
    if len(raw)+a.readout_warmup_cycles>a.max_readout_cycles:raise ValueError('Trigger/anchor intervals exceed max_readout_cycles')
    warm=[]
    if a.readout_warmup_cycles:
        first_frame=[r for r in raw if r['frame']==0]
        for index in range(-a.readout_warmup_cycles,0):
            f,local=divmod(index,len(first_frame));source=first_frame[local]
            warm.append({**source,'nominal_time_ns':source['nominal_time_ns']+f*frame_ns,'frame':f,
                         'column_id':f*n+source['column']})
    raw=warm+raw
    rng=np.random.default_rng(np.random.SeedSequence(cfg.rng_seed).spawn(3)[2])
    jitter=rng.normal(0,cfg.motion.laser_jitter_std_ns,len(raw))
    nominal=np.array([r['nominal_time_ns'] for r in raw])
    emitted=nominal+cfg.motion.laser_time_offset_ns+jitter
    mech,angle,velocity,active=mirror_pose(cfg.scan,emitted)
    _,encoder,_,_=mirror_pose(cfg.scan,nominal-cfg.motion.encoder_latency_ns)
    encoder=encoder+cfg.motion.encoder_angle_offset_mrad
    source_times=[emitted[i] for i,r in enumerate(raw) if r['has_pulse']]
    if np.any(np.diff(source_times)<=0):raise ValueError('Timing jitter/offset reorders source pulses')
    intervals=[]
    if cfg.exposure.gate_mode=='column':
        intervals=[(c['start_ns'],c['end_ns']) for c in columns]
        intervals.extend((f*frame_ns+c*slot_ns,f*frame_ns+(c+1)*slot_ns)
                         for f,c in {(r['frame'],r['column']) for r in warm})
    else:
        intervals=[(r['nominal_time_ns']+cfg.timing.gate_start_ns,
                    r['nominal_time_ns']+cfg.timing.gate_start_ns+cfg.timing.gate_width_ns)
                   for r in raw if r['has_pulse']]
    unions=merge_intervals(intervals);ends=[hi for _,hi in unions]
    windows=[];segments={};rows=[]
    for i,r in enumerate(raw):
        start=r['nominal_time_ns'];end=raw[i+1]['nominal_time_ns'] if i+1<len(raw) else total_ns
        cycle=i-len(warm);j=bisect.bisect_right(ends,start);pieces=[]
        while j<len(unions) and unions[j][0]<end:
            lo=max(start,unions[j][0]);hi=min(end,unions[j][1])
            if hi>lo:pieces.append((lo,hi))
            j+=1
        lo=pieces[0][0] if pieces else start;hi=pieces[-1][1] if pieces else start
        windows.append(AcquisitionWindow(cycle,start,end,lo,hi,r['frame']>=0,lo,hi));segments[cycle]=pieces
        rows.append({**r,'cycle':cycle,'start_ns':start,'end_ns':end,'emission_time_ns':float(emitted[i]),
            'emitted':bool(r['has_pulse'] and r['energy_nj']>0),'measured':r['frame']>=0,
            'mechanical_angle_mrad':float(mech[i]),'true_tx_optical_mrad':float(angle[i]),
            'optical_velocity_mrad_per_ns':float(velocity[i]),'encoder_optical_mrad':float(encoder[i]),
            'encoder_angle_error_mrad':float(encoder[i]-angle[i]),'true_active':bool(active[i]),
            'gate_segments_ns':pieces})
    if len(windows)>a.max_readout_cycles:raise ValueError('Program exceeds cycle resource limit')
    by_col={}
    for row in rows:
        if row['measured']:by_col.setdefault(row['column_id'],[]).append(row)
    for c in columns:
        owned=by_col[c['column_id']]
        c['cycles']=[r['cycle'] for r in owned]
        c['pulse_count']=sum(r['has_pulse'] for r in owned)
        # Complete the required nominal gate, even if it reaches the next column.
        if cfg.exposure.gate_mode=='per_pulse':
            requested=[r['nominal_time_ns']+cfg.timing.gate_start_ns+cfg.timing.gate_width_ns for r in owned if r['has_pulse']]
            c['data_ready_ns']=max([c['end_ns'],*requested])
        else:c['data_ready_ns']=c['end_ns']
    return GatedProgram(windows,segments),rows,columns,{
        **b,'duration_ns':total_ns,'frame_count':cfg.acquisition.frame_count,'column_count':len(columns),
        'trigger_count':sum(r['measured'] and r['has_pulse'] for r in rows),
        'emission_count':sum(r['measured'] and r['emitted'] for r in rows),
        'gate_union_exposure_ns':sum(hi-lo for w in windows if w.measured for lo,hi in segments[w.cycle]),
        'gate_observation_truncation_ns':sum(max(0,hi-total_ns) for lo,hi in unions if hi>total_ns),
        'clock_convention':'Column IDs identify output columns. Cycle IDs identify trigger references or dark anchors; phase is relative to the most recent reference, not hidden source identity.',
        'gate_convention':'Union of nominal gates; overlap counted once. Gate fragments retain the same trigger capacity cycle. Source/arrival tails continue across column boundaries.'}

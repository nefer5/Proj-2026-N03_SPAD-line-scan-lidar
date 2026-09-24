"""Column C composition using B optics and the shared continuous SPAD engine."""
from collections import defaultdict
import numpy as np
from ..constants import C
from ..contracts import CandidateEvents
from ..curves import Curve
from ..spad.source import sample_varying_candidates
from ..spad.device import effective_pde,apply_jitter
from ..spad.device.trace import TraceDevice
from ..spad.acquisition import evolve_program
from ..scan.column_schedule import build_column_schedule,FragmentAwareReadout,scheduled_energy,acquisition_scope
from ..scan.column_optics import ColumnPulseProjection
from ..scan.transport import transport_plan
from ..numerics.temporal import temporal_cdf
from ..processing.column_reconstruction import reconstruct_columns,histogram_for_records
from .spatial import project_illumination
from .scanning import channel_directions
from .lab import stamp_result


def noise_resource_probe(cfg,a,light,program):
    response=effective_pde(Curve(cfg.spectral_inputs.pde)(light.wavelength_nm),cfg.device.fill_factor)
    rates=light.background_photons_per_second@response+cfg.device.dcr_cps_per_spad+cfg.device.other_noise_cps_per_spad
    duration=sum(w.end_ns-w.start_ns if cfg.device.detector_operation=='free_running' else
                 sum(hi-lo for lo,hi in program.detector_intervals(w)) for w in program.windows)
    expected=float(rates.sum()*duration*1e-9)
    return {'expected_noise_candidates_lower_bound':expected,'event_limit':a.max_readout_events_per_run,
        'blocked':expected>a.max_readout_events_per_run,'includes_warmup':True,
        'note':'Signal candidates are additional. No background or source is silently disabled to meet resource limits.'}


def quantize_column_records(cfg,program,raw,electronic_seed,schedule):
    by_cycle={r['cycle']:r for r in schedule};windows={w.cycle:w for w in program.windows}
    phases=apply_jitter(np.random.default_rng(electronic_seed),np.array([r['phase_ns'] for r in raw]),cfg.readout.other_jitter_fwhm_ps)
    width=cfg.readout.tdc_bin_ps*1e-3;origin=cfg.timing.gate_start_ns;records=[]
    for r,phase in zip(raw,phases):
        w=windows[r['cycle']];time=w.start_ns+phase
        segment=next(((lo,hi) for lo,hi in program.detector_intervals(w) if lo<=time<hi),None)
        if segment is None:continue
        code=int(np.floor((phase-origin)/width))
        left=max(origin+code*width,segment[0]-w.start_ns,0.)
        right=min(origin+(code+1)*width,segment[1]-w.start_ns,w.end_ns-w.start_ns)
        if right<=left:continue
        row=by_cycle[r['cycle']]
        records.append({'cycle':r['cycle'],'column_id':row['column_id'],'frame':row['frame'],'column':row['column'],
            'pulse_reference':row['pulse_index'],'channel':r['channel'],'tdc':r['tdc'],'tdc_code':code,
            'phase_ns':float((left+right)/2),'time_ns':float(w.start_ns+(left+right)/2),
            'interval_start_ns':float(left),'interval_end_ns':float(right)})
    return records


def _single(cfg,a,progress,cancelled,*,optical_inputs=None,reconstruct=True):
    program,schedule,columns,budget=build_column_schedule(cfg,a)
    all_columns=columns
    program,schedule,columns,budget=acquisition_scope(cfg,a,program,schedule,columns,budget)
    light,groups,info=project_illumination(cfg,a,progress,cancelled) if optical_inputs is None else optical_inputs
    probe=noise_resource_probe(cfg,a,light,program)
    if probe['blocked']:raise ValueError(f"Noise candidates alone exceed limit: {probe['expected_noise_candidates_lower_bound']:.0f} > {a.max_readout_events_per_run}; adjust explicit conditions or limits")
    from ..processing.column_reconstruction import histogram_bin_count
    bins=histogram_bin_count(cfg,cfg.analysis_bin_ps)
    if bins>a.max_histogram_bins or bins*len(columns)*cfg.spad.channels_h*cfg.spad.channels_v>a.max_column_histogram_work:
        raise ValueError('Acquisition analysis exceeds histogram limits; select an explicit column scope or coarser analysis bin')
    projection=ColumnPulseProjection(cfg,a,light,groups,info,schedule)
    streams=np.random.SeedSequence(cfg.rng_seed).spawn(3)
    events,source=sample_varying_candidates(projection,light,cfg.device,Curve(cfg.spectral_inputs.pde),program,
        np.random.default_rng(streams[0]),a.max_readout_events_per_run,a.max_column_sampling_work,progress,cancelled,
        progress_stride=a.acquisition_block_cycles)
    device=TraceDevice(len(groups),cfg.diagnostics,program,a.readout_trace_events)
    session=evolve_program(cfg.device,cfg.readout,groups,program,events,a,progress,cancelled,
                           readout_factory=FragmentAwareReadout,device_engine=device)
    records=quantize_column_records(cfg,program,session.readout.records,streams[1],schedule)
    audit={**session.stats,'final_records':len(records),'timestamp_outside_gate_losses':len(session.readout.records)-len(records),
        'source':source,'trace':session.readout.trace,'device_trace':device.trace,
        'device_trace_selected_events':device.selected_events,'device_trace_truncated':device.selected_events>len(device.trace),
        'trace_truncated':session.stats['logic_triggers']>len(session.readout.trace)}
    if not reconstruct:return {'records':records,'audit':audit,'seed':cfg.rng_seed}
    directions=channel_directions(cfg,info)
    reconstruction=reconstruct_columns(cfg,a,records,schedule,columns,directions,projection.truth)
    complete=len(columns)==len(all_columns)
    transport=transport_plan(cfg,all_columns,record_counts=reconstruction['record_counts_by_column'] if complete else None)
    budget.update(scheduled_energy(cfg,schedule,budget['observation_end_ns'],start_ns=budget['observation_start_ns']))
    delivered={r['column_id'] for r in transport['rows'] if r['status']=='scheduled'} if transport['status'] in ('scheduled','overloaded') else None
    result={'records':records,'audit':audit,'optics':info,'record_schema':{'version':2,
        'time_basis':'most recent nominal trigger/anchor reference; absolute time also retained','tdc_bin_ps':cfg.readout.tdc_bin_ps,
        'tdc_origin_ns':cfg.timing.gate_start_ns,'pixel_identity':'raw records expose readout/TDC identity only; selected device trace is separate',
        'gate_union':'Predecessor gates can continue into a reference interval; signed TDC codes relative to the configured gate origin are allowed.'},
        'column_scan':{'columns':columns,'schedule':[r for r in schedule if r['measured']],
            'warmup_schedule':[r for r in schedule if not r['measured']],'frame_budget':budget,
            'channel_directions_mrad':directions,'pulse_optical_audit':projection.trace,
            'source_truth_by_cycle':{str(k):{n:v.tolist() for n,v in val.items()} for k,val in projection.truth.items()},
            'signal_budget_total':projection.budget_totals,'projection_work':projection.work,'projection_cache_hits':projection.cache_hits,
            'measured_column_ids':[c['column_id'] for c in columns],
            'pixel_signal_photons_total':projection.pixel_photons.tolist(),**reconstruction,'transport':transport,
            'delivered_point_cloud':None if delivered is None else [r for r in reconstruction['point_cloud'] if r['column_id'] in delivered]},
        'limitations':['World yaw uses 3D ray rotation; B receiver validity bounds apply to local incidence, not total HFOV.',
            'Optical poses are evaluated at pulse/echo centers. Temporal tails continue through the event engine; intrapulse scanning smear is not resolved.',
            'Background is uniform in the receiver-local angular domain; no guessed global scene/sky map.',
            'Finite warmup and observation. Out-of-interval source tails are counted and discarded without renormalization.',
            'Column lock waits for nominal recording gates. Record attribution follows observed trigger/anchor references, not hidden photon source.',
            'Unthresholded range estimates; no column-C Pd/PFA calibration or hidden-truth correction.']}
    from ..reporting.column_flow import build_column_flow
    result['photon_flow']=build_column_flow(cfg,result)
    return result


def run_columns(cfg,a,progress,cancelled):
    optical=project_illumination(cfg,a,progress,cancelled)
    main=_single(cfg,a,progress,cancelled,optical_inputs=optical)
    if main['audit']['source']['expected_work']*(cfg.acquisition.trial_count+cfg.acquisition.noise_trial_count)>a.max_column_analysis_candidates:
        raise ValueError('Requested repeat/noise candidate workload exceeds max_column_analysis_candidates')
    samples=[main['records']];noise=[];seeds=[cfg.rng_seed];noise_seeds=[];record_count=len(main['records'])
    roots=np.random.SeedSequence(cfg.rng_seed).spawn(max(a.lab_analysis_seed_streams.values())+1)
    for kind,count,stream in [('trials',cfg.acquisition.trial_count-1,a.lab_analysis_seed_streams['trials']),
                               ('noise',cfg.acquisition.noise_trial_count,a.lab_analysis_seed_streams['noise'])]:
        for seed_sequence in roots[stream].spawn(count):
            seed=int(seed_sequence.generate_state(1)[0]);acq=cfg.acquisition.model_copy(update={'rng_seed':seed})
            current=cfg.model_copy(update={'acquisition':acq})
            if kind=='noise':current=current.model_copy(update={'exposure':cfg.exposure.model_copy(update={'pulses':[p.model_copy(update={'energy_nj':0.}) for p in cfg.exposure.pulses]})})
            out=_single(current,a,progress,cancelled,optical_inputs=optical,reconstruct=False)
            record_count+=len(out['records'])
            if record_count>a.max_column_analysis_events:raise ValueError('Saved repeat/noise events exceed analysis resource limit')
            if kind=='noise':noise.append(out['records']);noise_seeds.append(seed)
            else:samples.append(out['records']);seeds.append(seed)
    main['statistics']={'trial_count':len(samples),'noise_trial_count':len(noise),'trial_seeds':seeds,'noise_seeds':noise_seeds,
                        'trial_records':samples,'noise_records':noise,'method':'Independent full-program realizations; extrema are computed after selecting/rebinning each realization.'}
    return stamp_result('C_column_scan',cfg,a,main)

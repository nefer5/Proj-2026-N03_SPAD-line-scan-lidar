"""Event-level digital SPAD readout families; no chip-specific mappings."""
import numpy as np
from .constants import C, FWHM_TO_SIGMA


def route_events(cfg, times, pixels, trace_limit=0):
    order=np.argsort(times,kind="stable")
    times=np.asarray(times)[order]; pixels=np.asarray(pixels)[order]
    period=1e9/cfg.laser_prf_hz
    independent=cfg.readout_mode.startswith("independent")
    gate_has_gap=cfg.gate_start_ns>0 or cfg.gate_width_ns<period
    count=cfg.spads_per_channel if independent else (cfg.tdc_count if cfg.readout_mode=="shared_multitdc" else 1)
    spad_ready=np.full(cfg.spads_per_channel,-np.inf)
    tdc_ready=np.full(count,-np.inf); hits=np.zeros(count,dtype=int); last_cycle=None
    timestamps=[]; candidates=[]; trace=[]
    stats={key:0 for key in ("potential_events","spad_dead_losses","outside_gate_avalanches","avalanches","logic_triggers","tdc_dead_losses","capacity_losses","recorded")}
    for t,p in zip(times,pixels):
        cycle=int(np.floor(t/period)); phase=t-cycle*period
        inside=cfg.gate_start_ns<=phase<cfg.gate_start_ns+cfg.gate_width_ns
        if cfg.detector_operation=="gated" and not inside: continue
        measured=0<=cycle<cfg.laser_shots
        if measured:stats["potential_events"]+=1
        if t<spad_ready[p]:
            if measured:stats["spad_dead_losses"]+=1
            continue
        spad_ready[p]=t+cfg.spad_dead_time_ns
        if measured:stats["avalanches"]+=1
        if not inside:
            if measured:stats["outside_gate_avalanches"]+=1
            continue
        candidates.append((float(t),int(p),cycle))

    triggers=[]
    if independent:
        triggers=[(t,p,cycle) for t,p,cycle in candidates]
    elif cfg.readout_mode=="coincidence_fixed":
        windows={}
        for t,p,cycle in candidates:
            index=int(np.floor((t-cycle*period-cfg.gate_start_ns)/cfg.coincidence_window_ns))
            windows.setdefault((cycle,index),set()).add(p)
        for (cycle,index),active in sorted(windows.items()):
            if len(active)>=cfg.coincidence_threshold:
                end=min(cfg.gate_start_ns+(index+1)*cfg.coincidence_window_ns,
                        cfg.gate_start_ns+cfg.gate_width_ns)
                triggers.append((float(np.nextafter(cycle*period+end,-np.inf)),0,cycle))
    elif cfg.readout_mode=="coincidence_sliding":
        active={}; last=None
        for t,p,cycle in candidates:
            if cycle!=last and gate_has_gap:active={}
            last=cycle
            active={cell:expiry for cell,expiry in active.items() if expiry>t}
            before=len(active)
            active[p]=t+cfg.coincidence_window_ns
            if before<cfg.coincidence_threshold<=len(active):triggers.append((t,0,cycle))
    else:
        end=-np.inf; previous=None
        for t,p,cycle in candidates:
            if cycle!=previous and gate_has_gap:end=-np.inf
            previous=cycle
            if t>=end:triggers.append((t,0,cycle))
            end=max(end,t+cfg.or_pulse_width_ns)

    for t,p,cycle in triggers:
        if cycle!=last_cycle:hits[:]=0;last_cycle=cycle
        measured=0<=cycle<cfg.laser_shots
        if measured:stats["logic_triggers"]+=1
        cap=1 if cfg.readout_mode.endswith("first") else cfg.tdc_max_hits_per_cycle
        choices=[p] if independent else list(range(count))
        available=[i for i in choices if t>=tdc_ready[i] and hits[i]<cap]
        outcome="recorded"; channel=None
        if not available:
            capacity=all(hits[i]>=cap for i in choices)
            outcome="capacity_loss" if capacity else "tdc_dead_loss"
            if measured:stats["capacity_losses" if capacity else "tdc_dead_losses"]+=1
        else:
            channel=min(available,key=lambda i:(tdc_ready[i],i))
            tdc_ready[channel]=t+cfg.tdc_dead_time_ns
            hits[channel]+=1
            if measured:
                timestamps.append(t-cycle*period);stats["recorded"]+=1
        if measured and len(trace)<trace_limit:
            trace.append({"cycle":cycle,"trigger_time_ns":t-cycle*period,"tdc":channel,"outcome":outcome})
    stats["logic_rejected_or_merged"]=stats["avalanches"]-stats["outside_gate_avalanches"]-stats["logic_triggers"]
    return np.array(timestamps),stats,trace


def event_histogram(cfg,budget,rng,algorithms,edges,signal=True,trace=False):
    period=1e9/cfg.laser_prf_hz
    warmup=algorithms.readout_warmup_cycles
    duration=period if cfg.detector_operation=="free_running" else cfg.gate_width_ns
    noise_mu=(budget.background_detected_per_gate+budget.dark_detected_per_gate+budget.other_detected_per_gate)*duration/cfg.gate_width_ns
    tof=2*cfg.range_m/C*1e9+cfg.calibration_delay_ns
    all_times=[];all_pixels=[]
    raw_count=0
    for cycle in range(-warmup,cfg.laser_shots):
        ns=int(rng.poisson(budget.signal_detected_per_pulse)) if signal else 0
        nb=int(rng.poisson(noise_mu))
        raw_count+=ns+nb
        if raw_count>algorithms.max_readout_events_per_run:
            raise ValueError("Event count exceeds configured limit; reduce flux, pulses or gate duration")
        laser=(rng.normal(0,cfg.pulse_fwhm_ps/FWHM_TO_SIGMA,ns) if cfg.pulse_shape=="gaussian"
               else rng.uniform(-cfg.pulse_fwhm_ps/2,cfg.pulse_fwhm_ps/2,ns))*1e-3
        sig=tof+laser+rng.normal(0,cfg.spad_jitter_fwhm_ps/FWHM_TO_SIGMA*1e-3,ns)
        start=0 if cfg.detector_operation=="free_running" else cfg.gate_start_ns
        noise=start+rng.uniform(0,duration,nb)
        all_times.extend(np.r_[sig,noise]+cycle*period)
        all_pixels.extend(rng.integers(0,cfg.spads_per_channel,ns+nb))
    timestamps,stats,log=route_events(cfg,all_times,all_pixels,algorithms.readout_trace_events if trace else 0)
    # Electronics timing noise is applied only to recorded timestamps, not SPAD recovery.
    timestamps=timestamps+rng.normal(0,cfg.other_jitter_fwhm_ps/FWHM_TO_SIGMA*1e-3,len(timestamps))
    hist=np.histogram(timestamps,bins=edges)[0].astype(float)
    stats["timestamp_outside_gate_losses"]=stats["recorded"]-int(hist.sum())
    return hist,stats,log


def readout_work_estimate(cfg,budget,algorithms):
    period=1e9/cfg.laser_prf_hz
    ratio=period/cfg.gate_width_ns if cfg.detector_operation=="free_running" else 1
    noise=(budget.background_detected_per_gate+budget.dark_detected_per_gate+budget.other_detected_per_gate)*ratio
    signal_runs=1+max(cfg.monte_carlo_trials-1,0)+algorithms.readout_expected_trials
    noise_runs=algorithms.readout_expected_trials+(algorithms.detector_calibration_trials+algorithms.detector_null_trials if cfg.detection_enabled else 0)
    cycles=cfg.laser_shots+algorithms.readout_warmup_cycles
    return {'runs':signal_runs+noise_runs,'cycles':cycles*(signal_runs+noise_runs),
            'events':cycles*((budget.signal_detected_per_pulse+noise)*signal_runs+noise*noise_runs)}


def event_acquisition(cfg,budget,algorithms,edges):
    workload=readout_work_estimate(cfg,budget,algorithms)
    if workload['cycles']>algorithms.max_readout_cycles:
        raise ValueError('Cycle work exceeds configured limit; reduce pulse count or repetitions')
    if workload['events']>algorithms.max_readout_expected_work:
        raise ValueError("Event simulation work exceeds configured limit; reduce repetitions/flux or use analytic_reference")
    seeds=np.random.SeedSequence(cfg.rng_seed).spawn(4)
    observation_rng,trial_rng,mean_rng,noise_rng=[np.random.default_rng(s) for s in seeds]
    observed,stats,trace=event_histogram(cfg,budget,observation_rng,algorithms,edges,trace=True)
    expected=np.zeros_like(observed);noise=np.zeros_like(observed)
    for _ in range(algorithms.readout_expected_trials):
        sample=event_histogram(cfg,budget,mean_rng,algorithms,edges)
        expected+=sample[0]
        noise+=event_histogram(cfg,budget,noise_rng,algorithms,edges,signal=False)[0]
    trial_histograms=([observed.copy()]+[event_histogram(cfg,budget,trial_rng,algorithms,edges)[0]
                       for _ in range(cfg.monte_carlo_trials-1)]) if cfg.monte_carlo_trials else []
    return observed,expected/algorithms.readout_expected_trials,noise/algorithms.readout_expected_trials,trial_histograms,{
        "mode":cfg.readout_mode,"engine":"event_monte_carlo",
        "expected_trials":algorithms.readout_expected_trials,"warmup_cycles":algorithms.readout_warmup_cycles,
        "losses":stats,"trace":trace,"trace_truncated":stats["logic_triggers"]>len(trace),
        "note":"MC mean is not an exact expectation. Nonparalyzable dead times; gate controls TDC input; free_running allows out-of-gate SPAD avalanches. Coincidence counts distinct cells. No afterpulse or avalanche crosstalk yet.",
    }

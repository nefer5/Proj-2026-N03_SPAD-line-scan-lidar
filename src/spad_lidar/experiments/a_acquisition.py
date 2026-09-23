"""A source adapter preserves historical RNG ordering; routes through the shared detector core."""
import numpy as np
from ..constants import C, FWHM_TO_SIGMA
from .a_router import route_events

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

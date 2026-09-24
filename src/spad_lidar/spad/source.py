"""Photon arrival sampler: consumes detector-plane measures, never optical parameters."""
import numpy as np
from ..constants import FWHM_TO_SIGMA
from ..contracts import CandidateEvents
from .device import effective_pde, apply_jitter
from ..numerics.temporal import sample_pulse_offsets


def draw_cycle_events(rng, signal_counts, noise_counts, centers_ns, pulse_shape, pulse_fwhm_ps,
                      device_jitter_ps, noise_start_ns, noise_duration_ns,*,tail=None,noise_intervals=None):
    """Common temporal/pixel sampler used by static and time-varying illumination."""
    times_out=[];pixels_out=[]
    # Empty draws consume no RNG state; skip zero-count pixels without changing
    # the numerical protocol or event ordering of any active pixel.
    for pixel in np.flatnonzero(signal_counts.sum(axis=0)+noise_counts):
        pieces=[]
        for component in np.flatnonzero(signal_counts[:,pixel]):
            n=int(signal_counts[component,pixel])
            offsets=sample_pulse_offsets(rng,pulse_shape,pulse_fwhm_ps,n)
            if tail is not None:
                delayed=rng.random(n)<tail[0]
                offsets[delayed]+=rng.exponential(tail[1],int(delayed.sum()))
            pieces.append(apply_jitter(rng,centers_ns[component]+offsets,device_jitter_ps))
        noise=noise_start_ns+rng.uniform(0,noise_duration_ns,int(noise_counts[pixel]))
        if noise_intervals is not None and len(noise):
            lengths=np.array([hi-lo for lo,hi in noise_intervals]);cumulative=np.cumsum(lengths)
            coordinates=noise-noise_start_ns
            intervals=np.searchsorted(cumulative,coordinates,side='right')
            previous=np.r_[0,cumulative[:-1]]
            noise=np.array([lo for lo,hi in noise_intervals])[intervals]+coordinates-previous[intervals]
        times_out.extend(np.concatenate([*pieces,noise]))
        pixels_out.extend([pixel]*(int(signal_counts[:,pixel].sum())+int(noise_counts[pixel])))
    return times_out,pixels_out


def sample_candidates(illumination, device, pde_curve, program, rng, event_limit):
    response = effective_pde(pde_curve(illumination.wavelength_nm), device.fill_factor)
    signal = illumination.signal_photons_per_pulse @ response
    optical_background = illumination.background_photons_per_second @ response
    noise_rate = optical_background + device.dcr_cps_per_spad + device.other_noise_cps_per_spad
    total_expected = 0.0
    for w in program.windows:
        duration = (w.end_ns-w.start_ns) if device.detector_operation == 'free_running' else (w.gate_close_ns-w.gate_open_ns)
        total_expected += signal.sum()+noise_rate.sum()*duration*1e-9
    if total_expected > event_limit:
        raise ValueError('Expected candidate count exceeds event resource limit; no automatic approximation')
    all_times, all_pixels = [], []
    count = 0
    for w in program.windows:
        duration = (w.end_ns-w.start_ns) if device.detector_operation == 'free_running' else (w.gate_close_ns-w.gate_open_ns)
        start = w.start_ns if device.detector_operation == 'free_running' else w.gate_open_ns
        ns = rng.poisson(signal)
        nb = rng.poisson(noise_rate*duration*1e-9)
        count += int(ns.sum()+nb.sum())
        if count > event_limit:
            raise ValueError('Actual candidate count exceeds event resource limit')
        times,pixels=draw_cycle_events(rng,ns[None,:],nb,[w.start_ns+illumination.pulse_delay_ns],
            illumination.pulse_shape,illumination.pulse_fwhm_ps,device.spad_jitter_fwhm_ps,start,duration)
        all_times.extend(times);all_pixels.extend(pixels)
    times = np.asarray(all_times)
    pixels = np.asarray(all_pixels, dtype=int)
    inside = (times >= program.windows[0].start_ns) & (times < program.windows[-1].end_ns)
    audit = {'expected_signal_candidates_per_pixel_per_pulse': signal.tolist(),
             'expected_optical_background_candidates_per_pixel_per_second': optical_background.tolist(),
             'expected_dark_candidates_per_pixel_per_second': device.dcr_cps_per_spad,
             'expected_other_candidates_per_pixel_per_second': device.other_noise_cps_per_spad,
             'expected_work': float(total_expected), 'sampled_candidates': count,
             'outside_simulation_interval': int((~inside).sum()),
             'note': 'PDE/FF applied by device. Noise includes dark and explicit electronic candidates. Finite warmup; boundary tails are discarded without renormalization.'}
    return CandidateEvents(times[inside], pixels[inside]), audit


def sample_varying_candidates(signal_provider, background, device, pde_curve, program, rng,
                              event_limit, sampling_work_limit, progress, cancelled,*,progress_stride=None):
    response=effective_pde(pde_curve(background.wavelength_nm),device.fill_factor)
    optical_noise=background.background_photons_per_second@response
    noise_rate=optical_noise+device.dcr_cps_per_spad+device.other_noise_cps_per_spad
    times=[];pixels=[];count=0;expected=0.;work=0;expected_signal=[]
    for index,w in enumerate(program.windows):
        if cancelled():
            raise InterruptedError('Cancelled during time-varying illumination')
        pulse=signal_provider(w)
        if pulse.photons_per_pixel.shape[1]!=len(noise_rate):
            raise ValueError('Pulse pixel topology differs from detector/background')
        signal=pulse.photons_per_pixel*effective_pde(pde_curve(pulse.wavelength_nm),device.fill_factor)[:,None]
        work+=signal.size+noise_rate.size
        if work>sampling_work_limit:
            raise ValueError('Time-varying photon sampling exceeds configured work limit')
        gate_provider=getattr(program,'detector_intervals',None)
        gate_intervals=gate_provider(w) if gate_provider is not None and device.detector_operation=='gated' else None
        duration=(sum(hi-lo for lo,hi in gate_intervals) if gate_intervals is not None else
                  w.end_ns-w.start_ns if device.detector_operation=='free_running' else w.gate_close_ns-w.gate_open_ns)
        start=w.start_ns if device.detector_operation=='free_running' else w.gate_open_ns
        expected+=float(signal.sum()+noise_rate.sum()*duration*1e-9)
        if expected>event_limit:
            raise ValueError('Expected candidate count exceeds event limit; no approximation was substituted')
        ns=rng.poisson(signal);nb=rng.poisson(noise_rate*duration*1e-9)
        count+=int(ns.sum()+nb.sum())
        if count>event_limit:
            raise ValueError('Actual candidate count exceeds event resource limit')
        t,p=draw_cycle_events(rng,ns,nb,pulse.arrival_center_ns,pulse.pulse_shape,pulse.pulse_fwhm_ps,
                              device.spad_jitter_fwhm_ps,start,duration,tail=pulse.tail,noise_intervals=gate_intervals)
        times.extend(t);pixels.extend(p)
        if w.measured:
            expected_signal.append({'cycle':w.cycle,'per_pixel':signal.sum(axis=0).tolist()})
        if progress_stride is None or (index+1)%progress_stride==0 or index+1==len(program.windows):
            progress(index+1,len(program.windows),'逐发光学与光子采样')
    times=np.asarray(times);pixels=np.asarray(pixels,dtype=int)
    inside=(times>=program.windows[0].start_ns)&(times<program.windows[-1].end_ns)
    audit={'expected_signal_candidates_by_cycle':expected_signal,
           'expected_optical_background_candidates_per_pixel_per_second':optical_noise.tolist(),
           'expected_dark_candidates_per_pixel_per_second':device.dcr_cps_per_spad,
           'expected_other_candidates_per_pixel_per_second':device.other_noise_cps_per_spad,
           'expected_work':expected,'sampling_work':work,'sampled_candidates':count,
           'outside_simulation_interval':int((~inside).sum()),
           'note':'All sources enter the same persistent device/readout session. Background is uniform in the receiver-local angular domain. Finite observation tails are discarded, not renormalized.'}
    return CandidateEvents(times[inside],pixels[inside]),audit

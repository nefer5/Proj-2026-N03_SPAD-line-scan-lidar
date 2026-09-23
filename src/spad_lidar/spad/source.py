"""Photon arrival sampler: consumes detector-plane measures, never optical parameters."""
import numpy as np
from ..constants import FWHM_TO_SIGMA
from ..contracts import CandidateEvents
from .device import effective_pde, apply_jitter
from ..numerics.temporal import sample_pulse_offsets


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
        for pixel in range(len(signal)):
            n = int(ns[pixel])
            offsets = sample_pulse_offsets(rng, illumination.pulse_shape, illumination.pulse_fwhm_ps, n)
            times = apply_jitter(rng, w.start_ns+illumination.pulse_delay_ns+offsets, device.spad_jitter_fwhm_ps)
            noise = start+rng.uniform(0, duration, int(nb[pixel]))
            all_times.extend(np.r_[times, noise])
            all_pixels.extend([pixel]*(n+int(nb[pixel])))
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

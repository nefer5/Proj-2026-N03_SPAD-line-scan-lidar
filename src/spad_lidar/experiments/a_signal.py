"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from scipy.special import ndtr
from ..rx.budget import photon_budget
from ..spad.analytical import _first_photon_probabilities


from ..numerics.temporal import timing_sigma_ns


def _time_axis(cfg):
    width = cfg.tdc_bin_ps * 1e-3
    # Do not extend the gate if its width is not an integer multiple of the TDC bin.
    n = int(np.ceil(cfg.gate_width_ns / width))
    edges = cfg.gate_start_ns + np.arange(n + 1) * width
    edges[-1] = cfg.gate_start_ns + cfg.gate_width_ns
    return edges, (edges[:-1] + edges[1:]) / 2


def _signal_shape(cfg, edges_ns, range_m=None):
    r = cfg.range_m if range_m is None else range_m
    tof = 2 * r / C * 1e9 + cfg.calibration_delay_ns
    x = edges_ns - tof
    if cfg.pulse_shape == "gaussian":
        cdf = ndtr(x / timing_sigma_ns(cfg))
    else:
        width = cfg.pulse_fwhm_ps * 1e-3
        jitter = np.hypot(cfg.spad_jitter_fwhm_ps, cfg.other_jitter_fwhm_ps) / FWHM_TO_SIGMA * 1e-3
        if jitter == 0:
            cdf = np.clip(x / width + 0.5, 0, 1)
        else:
            # Analytic CDF of Uniform(-width/2,width/2) convolved with Gaussian.
            def primitive(z):
                return z * ndtr(z) + np.exp(-z*z/2) / sqrt(2*pi)
            cdf = jitter / width * (primitive((x + width/2)/jitter)
                                    - primitive((x - width/2)/jitter))
    # The omitted tail is physically outside the gate. Never renormalize it.
    return np.maximum(np.diff(cdf), 0)


def _signal_pdf(cfg, time_ns):
    """Analytic signal IRF density, in 1/ns; no random draws or readout losses."""
    x=np.asarray(time_ns)-(2*cfg.range_m/C*1e9+cfg.calibration_delay_ns)
    if cfg.pulse_shape=='gaussian':
        sigma=timing_sigma_ns(cfg)
        return np.exp(-0.5*(x/sigma)**2)/(sqrt(2*pi)*sigma)
    width=cfg.pulse_fwhm_ps*1e-3
    jitter=np.hypot(cfg.spad_jitter_fwhm_ps,cfg.other_jitter_fwhm_ps)/FWHM_TO_SIGMA*1e-3
    if jitter==0:
        return (np.abs(x)<=width/2).astype(float)/width
    return (ndtr((x+width/2)/jitter)-ndtr((x-width/2)/jitter))/width


def _histogram_components(cfg, range_m=None):
    budget = photon_budget(cfg, range_m)
    edges, centers = _time_axis(cfg)
    shape = _signal_shape(cfg, edges, range_m)
    noise_total = (budget.background_detected_per_gate + budget.dark_detected_per_gate
                   + budget.other_detected_per_gate)
    mu_signal = budget.signal_detected_per_pulse * shape / cfg.spads_per_channel
    mu_noise = noise_total * np.diff(edges) / cfg.gate_width_ns / cfg.spads_per_channel
    mu = mu_signal + mu_noise
    probability = _first_photon_probabilities(mu)
    opportunities = cfg.laser_shots * cfg.spads_per_channel
    return {
        "budget": budget, "edges": edges, "time": centers, "shape": shape,
        "mu_signal": mu_signal, "mu_noise": mu_noise,
        "survival": np.exp(-np.r_[0.0, np.cumsum(mu[:-1])]),
        "probability": probability, "expected": probability * opportunities,
        "expected_noise": _first_photon_probabilities(mu_noise) * opportunities,
        "no_event_probability": float(np.exp(-mu.sum())),
    }


def expected_histogram(cfg, range_m=None):
    x = _histogram_components(cfg, range_m)
    return x["time"], x["expected"], x["expected_noise"], x["budget"]


def _preview_edges(edges, algorithms):
    """Subdivide every actual bin, including a shortened last bin, exactly."""
    factor=min(algorithms.histogram_preview_subdivisions,
               algorithms.max_histogram_preview_bins//(len(edges)-1))
    if factor<2:
        raise ValueError('max_histogram_preview_bins must allow at least two subdivisions per histogram bin')
    fractions=np.arange(factor)/factor
    fine=(edges[:-1,None]+np.diff(edges)[:,None]*fractions).ravel()
    return np.r_[fine,edges[-1]],factor


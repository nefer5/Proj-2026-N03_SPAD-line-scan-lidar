"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from scipy.signal import convolve
from ..configuration import Algorithms
from ..numerics.temporal import timing_sigma_ns


def _estimate_range(cfg, time_ns, hist, algorithms=None, with_trace=False):
    a = algorithms or Algorithms.load()
    baseline = float(np.median(hist))
    sigma_bins = max(timing_sigma_ns(cfg) / (cfg.tdc_bin_ps * 1e-3), a.estimator_min_sigma_bins)
    half_kernel = min(len(hist) - 1, max(1, int(np.ceil(a.estimator_kernel_sigma * sigma_bins))))
    x = np.arange(-half_kernel, half_kernel + 1)
    kernel = np.exp(-0.5 * (x / sigma_bins)**2)
    kernel /= kernel.sum()
    filtered = convolve(hist - baseline, kernel, mode="same")
    peak = int(np.argmax(filtered))
    half_centroid = max(1, int(np.ceil(a.estimator_centroid_sigma * sigma_bins)))
    lo, hi = max(0, peak-half_centroid), min(len(hist), peak+half_centroid+1)
    weights = np.maximum(hist[lo:hi]-baseline, 0)
    centroid = float(np.sum(time_ns[lo:hi] * weights) / weights.sum()) if weights.sum() > 0 else None
    estimate = (centroid-cfg.calibration_delay_ns)*1e-9*C/2 if centroid is not None else None
    score = float(max(filtered[peak], 0) / sqrt(max(baseline, a.snr_baseline_floor_counts)))
    if not with_trace:
        return estimate, score
    return estimate, score, {
        "baseline_counts": baseline, "smoothing_sigma_bins": sigma_bins,
        "kernel_weights": kernel.tolist(), "filtered_counts": filtered.tolist(),
        "peak_bin": peak, "centroid_bin_start": lo, "centroid_bin_end_exclusive": hi,
        "centroid_weights": weights.tolist(), "centroid_time_ns": centroid,
        "distance_m": estimate, "peak_score": score,
        "formula": "baseline=median(H); W=max(H-baseline,0); t=sum(t*W)/sum(W); R=c*(t-delay)/2",
        "note": "Gaussian smoothing is a search heuristic, including rectangular pulses. Peak score is not a calibrated detection SNR.",
    }


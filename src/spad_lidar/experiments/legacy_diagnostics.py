"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from ..configuration import Algorithms
from ..rx.budget import photon_budget
from .a_signal import timing_sigma_ns


def crosstalk_model(cfg):
    idx = np.arange(cfg.line_channels)
    distance = np.abs(idx[:, None] - idx[None, :])
    direct = cfg.nearest_neighbor_crosstalk * np.exp(-np.maximum(distance-1, 0)/cfg.crosstalk_decay_channels)
    np.fill_diagonal(direct, 0)
    radius = float(np.max(np.abs(np.linalg.eigvalsh(direct))))
    if radius >= 1:
        raise ValueError("Crosstalk branching matrix has spectral radius >= 1; reduce coupling")
    total = np.linalg.solve(np.eye(len(idx))-direct, np.eye(len(idx))) - np.eye(len(idx))
    return direct, total


def _range_sweep(cfg, algorithms=None):
    a = algorithms or Algorithms.load()
    min_gate_range = max(0.0, C*(cfg.gate_start_ns-cfg.calibration_delay_ns)*1e-9/2)
    max_range = C*(cfg.gate_start_ns+cfg.gate_width_ns-cfg.calibration_delay_ns)*1e-9/2
    low = max(a.sweep_min_range_m, cfg.range_m*a.sweep_low_ratio, min_gate_range)
    high = min(max_range*a.sweep_gate_margin_ratio, cfg.range_m*a.sweep_high_ratio)
    ranges = np.geomspace(low, high, a.sweep_points) if high > low else np.array([cfg.range_m])
    sigma_s = sqrt((timing_sigma_ns(cfg)*1e-9)**2+(cfg.tdc_bin_ps*1e-12)**2/12)
    points = []
    for r in ranges:
        b = photon_budget(cfg, float(r))
        s = b.signal_detected_per_pulse * cfg.laser_shots
        n = (b.background_detected_per_gate+b.dark_detected_per_gate+b.other_detected_per_gate)*cfg.laser_shots
        width = max(a.sweep_noise_width_sigma*timing_sigma_ns(cfg), cfg.tdc_bin_ps*1e-3)
        n_window = n*min(width/cfg.gate_width_ns, 1)
        points.append({
            "range_m": float(r), "signal_counts": s, "window_background_counts": n_window,
            "shot_noise_snr": s/sqrt(s+n_window) if s+n_window > 0 else 0,
            "ideal_precision_cm": C*sigma_s/2/sqrt(s)*100 if s > 0 else None,
        })
    return points


from __future__ import annotations

from dataclasses import dataclass
from math import pi

import numpy as np
from scipy.special import ndtr

from .models import SimulationConfig

C = 299_792_458.0
H = 6.626_070_15e-34


@dataclass(frozen=True)
class Budget:
    signal_detected_per_pulse: float
    background_detected_per_gate: float
    dark_detected_per_gate: float
    other_detected_per_gate: float
    filter_enbw_nm: float
    filter_transmission_at_laser: float


def _filter_properties(cfg: SimulationConfig) -> tuple[float, float]:
    if not cfg.filter_curve or len(cfg.filter_curve) < 2:
        return cfg.filter_bandwidth_nm * cfg.filter_peak_transmission, cfg.filter_peak_transmission

    points = sorted(cfg.filter_curve, key=lambda p: p.wavelength_nm)
    wl = np.asarray([p.wavelength_nm for p in points], dtype=float)
    tr = np.asarray([p.transmission for p in points], dtype=float)
    enbw = float(np.trapezoid(tr, wl))
    at_laser = float(np.interp(cfg.wavelength_nm, wl, tr, left=0.0, right=0.0))
    return max(enbw, 0.0), at_laser


def photon_budget(cfg: SimulationConfig, range_m: float | None = None) -> Budget:
    r = float(range_m if range_m is not None else cfg.range_m)
    wavelength_m = cfg.wavelength_nm * 1e-9
    photon_energy = H * C / wavelength_m
    aperture_area = pi * (cfg.rx_aperture_mm * 1e-3 / 2.0) ** 2
    enbw_nm, filter_at_laser = _filter_properties(cfg)

    # Extended Lambertian target. Current-channel pulse energy is the energy on the
    # target patch associated with the evaluated angular channel.
    emitted_j = cfg.pulse_energy_nj * 1e-9
    received_signal_j = (
        emitted_j
        * cfg.tx_efficiency
        * cfg.target_reflectivity
        * aperture_area
        / (pi * r**2)
        * cfg.rx_efficiency
        * filter_at_laser
        * cfg.overlap_factor
        * cfg.atmospheric_one_way_transmission**2
    )
    effective_pdp = cfg.pde * cfg.fill_factor
    signal = received_signal_j / photon_energy * effective_pdp

    omega_sr = (cfg.channel_ifov_h_mrad * 1e-3) * (cfg.channel_ifov_v_mrad * 1e-3)
    background_w = (
        cfg.background_spectral_radiance
        * aperture_area
        * omega_sr
        * enbw_nm
        * cfg.rx_efficiency
    )
    gate_s = cfg.gate_width_ns * 1e-9
    background = background_w * gate_s / photon_energy * effective_pdp
    dark = cfg.dcr_cps_per_spad * cfg.spads_per_channel * gate_s
    other = cfg.other_noise_cps_per_spad * cfg.spads_per_channel * gate_s

    return Budget(signal, background, dark, other, enbw_nm, filter_at_laser)


def _time_axis(cfg: SimulationConfig) -> tuple[np.ndarray, np.ndarray]:
    bin_ns = cfg.tdc_bin_ps * 1e-3
    n_bins = int(np.ceil(cfg.gate_width_ns / bin_ns))
    edges = cfg.gate_start_ns + np.arange(n_bins + 1, dtype=float) * bin_ns
    centers = (edges[:-1] + edges[1:]) / 2.0
    return edges, centers


def _signal_shape(cfg: SimulationConfig, edges_ns: np.ndarray, range_m: float | None = None) -> np.ndarray:
    r = float(range_m if range_m is not None else cfg.range_m)
    tof_ns = 2.0 * r / C * 1e9 + cfg.calibration_delay_ns
    fwhm_ps = np.sqrt(
        cfg.pulse_fwhm_ps**2 + cfg.spad_jitter_fwhm_ps**2 + cfg.other_jitter_fwhm_ps**2
    )
    sigma_ns = max(fwhm_ps / 2.354_820_045 / 1000.0, 1e-9)
    z_hi = (edges_ns[1:] - tof_ns) / sigma_ns
    z_lo = (edges_ns[:-1] - tof_ns) / sigma_ns
    weights = ndtr(z_hi) - ndtr(z_lo)
    total = float(weights.sum())
    if total <= 0:
        return np.zeros_like(weights)
    return weights / total


def _first_photon_probabilities(mu_per_bin_per_spad: np.ndarray) -> np.ndarray:
    # Inhomogeneous Poisson arrivals, one timestamp max per SPAD and laser shot.
    before = np.concatenate(([0.0], np.cumsum(mu_per_bin_per_spad[:-1])))
    return np.exp(-before) * (-np.expm1(-mu_per_bin_per_spad))


def expected_histogram(
    cfg: SimulationConfig, range_m: float | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Budget]:
    budget = photon_budget(cfg, range_m)
    edges, centers = _time_axis(cfg)
    shape = _signal_shape(cfg, edges, range_m)
    n_bins = len(centers)

    noise_total = budget.background_detected_per_gate + budget.dark_detected_per_gate + budget.other_detected_per_gate
    mu_signal = budget.signal_detected_per_pulse * shape / cfg.spads_per_channel
    mu_noise = np.full(n_bins, noise_total / n_bins / cfg.spads_per_channel)

    p_total = _first_photon_probabilities(mu_signal + mu_noise)
    p_noise = _first_photon_probabilities(mu_noise)
    opportunities = cfg.laser_shots * cfg.spads_per_channel
    return centers, p_total * opportunities, p_noise * opportunities, budget


def _estimate_range(cfg: SimulationConfig, time_ns: np.ndarray, hist: np.ndarray) -> tuple[float, float]:
    baseline = float(np.median(hist))
    fwhm_ps = np.sqrt(
        cfg.pulse_fwhm_ps**2 + cfg.spad_jitter_fwhm_ps**2 + cfg.other_jitter_fwhm_ps**2
    )
    sigma_bins = max((fwhm_ps / 2.35482) / cfg.tdc_bin_ps, 0.6)
    half_kernel = max(2, int(np.ceil(3.0 * sigma_bins)))
    x = np.arange(-half_kernel, half_kernel + 1)
    kernel = np.exp(-0.5 * (x / sigma_bins) ** 2)
    kernel /= kernel.sum()
    filtered = np.convolve(hist - baseline, kernel, mode="same")
    peak_idx = int(np.argmax(filtered))

    half_centroid = max(1, int(np.ceil(2.0 * sigma_bins)))
    lo = max(0, peak_idx - half_centroid)
    hi = min(len(hist), peak_idx + half_centroid + 1)
    weights = np.maximum(hist[lo:hi] - baseline, 0.0)
    if weights.sum() <= 0:
        return float("nan"), 0.0
    time_est_ns = float(np.sum(time_ns[lo:hi] * weights) / weights.sum())
    range_est = (time_est_ns - cfg.calibration_delay_ns) * 1e-9 * C / 2.0
    peak_snr = float(max(filtered[peak_idx], 0.0) / np.sqrt(max(baseline, 1.0)))
    return range_est, peak_snr


def _sample_histogram(rng: np.random.Generator, expected: np.ndarray, opportunities: int) -> np.ndarray:
    p = np.maximum(expected / opportunities, 0.0)
    p_sum = float(p.sum())
    if p_sum >= 1.0:
        p *= (1.0 - 1e-12) / p_sum
        p_sum = float(p.sum())
    sample = rng.multinomial(opportunities, np.append(p, 1.0 - p_sum))
    return sample[:-1].astype(float)


def crosstalk_model(cfg: SimulationConfig) -> tuple[np.ndarray, np.ndarray]:
    n = cfg.line_channels
    direct = np.zeros((n, n), dtype=float)
    for source in range(n):
        for victim in range(n):
            distance = abs(source - victim)
            if distance:
                direct[victim, source] = cfg.nearest_neighbor_crosstalk * np.exp(
                    -(distance - 1) / cfg.crosstalk_decay_channels
                )

    # Ensure a subcritical branching process. Matrix element [victim, source]
    # is the probability/mean of a direct secondary avalanche.
    max_col_sum = float(direct.sum(axis=0).max())
    if max_col_sum >= 0.95:
        direct *= 0.95 / max_col_sum
    total_induced = np.linalg.inv(np.eye(n) - direct) - np.eye(n)
    return direct, total_induced


def _range_sweep(cfg: SimulationConfig) -> list[dict[str, float]]:
    max_range = C * (cfg.gate_start_ns + cfg.gate_width_ns - cfg.calibration_delay_ns) * 1e-9 / 2.0
    low = max(1.0, cfg.range_m * 0.35)
    high = min(max_range * 0.98, max(cfg.range_m * 2.0, low * 1.2))
    ranges = np.geomspace(low, high, 28) if high > low else np.array([cfg.range_m])
    fwhm_ps = np.sqrt(
        cfg.pulse_fwhm_ps**2 + cfg.spad_jitter_fwhm_ps**2 + cfg.other_jitter_fwhm_ps**2
    )
    sigma_time_s = np.sqrt((fwhm_ps / 2.35482 * 1e-12) ** 2 + (cfg.tdc_bin_ps * 1e-12) ** 2 / 12.0)
    points: list[dict[str, float]] = []
    for r in ranges:
        budget = photon_budget(cfg, float(r))
        s = budget.signal_detected_per_pulse * cfg.laser_shots
        n_total_gate = (
            budget.background_detected_per_gate
            + budget.dark_detected_per_gate
            + budget.other_detected_per_gate
        ) * cfg.laser_shots
        effective_width_ns = max(fwhm_ps / 1000.0 * 2.0, cfg.tdc_bin_ps / 1000.0)
        n_window = n_total_gate * min(effective_width_ns / cfg.gate_width_ns, 1.0)
        snr = s / np.sqrt(max(s + n_window, 1e-30))
        sigma_range_m = C * sigma_time_s / 2.0 / np.sqrt(max(s, 1e-30))
        points.append(
            {
                "range_m": float(r),
                "signal_counts": float(s),
                "window_background_counts": float(n_window),
                "shot_noise_snr": float(snr),
                "ideal_precision_cm": float(sigma_range_m * 100.0),
            }
        )
    return points


def simulate(cfg: SimulationConfig) -> dict:
    time_ns, expected, expected_noise, budget = expected_histogram(cfg)
    rng = np.random.default_rng(cfg.rng_seed)
    opportunities = cfg.laser_shots * cfg.spads_per_channel
    observed = _sample_histogram(rng, expected, opportunities)
    estimated_range, peak_snr = _estimate_range(cfg, time_ns, observed)

    trial_estimates: list[float] = []
    trial_snrs: list[float] = []
    for _ in range(cfg.monte_carlo_trials):
        h = _sample_histogram(rng, expected, opportunities)
        r_est, snr = _estimate_range(cfg, time_ns, h)
        if np.isfinite(r_est):
            trial_estimates.append(r_est)
            trial_snrs.append(snr)

    estimates = np.asarray(trial_estimates)
    if estimates.size:
        errors = estimates - cfg.range_m
        tolerance_m = max(0.20, C * cfg.pulse_fwhm_ps * 1e-12)
        success = np.abs(errors) <= tolerance_m
        bias_cm = float(np.mean(errors) * 100.0)
        precision_cm = float(np.std(estimates, ddof=1) * 100.0) if estimates.size > 1 else 0.0
        success_rate = float(np.mean(success))
    else:
        bias_cm = precision_cm = float("nan")
        success_rate = 0.0

    direct_xt, total_xt = crosstalk_model(cfg)
    source = cfg.line_channels // 2
    victim_profile = total_xt[:, source]

    return {
        "assumptions": [
            "脉冲能量是当前扫描角通道照到目标上的能量。",
            "目标为正入射、足够大的朗伯散射面，忽略遮挡和多径。",
            "每个 SPAD 每发最多记录一个时间戳，采用首光子 TCSPC 模型。",
            "环境光在门宽内时间均匀，并由场景光谱辐亮度计算。",
            "串扰模型是雪崩触发的平稳分支模型，不包含版图方向性和延迟分布。",
        ],
        "budget": {
            "signal_detected_per_pulse": budget.signal_detected_per_pulse,
            "background_detected_per_gate": budget.background_detected_per_gate,
            "dark_detected_per_gate": budget.dark_detected_per_gate,
            "other_detected_per_gate": budget.other_detected_per_gate,
            "filter_enbw_nm": budget.filter_enbw_nm,
            "filter_transmission_at_laser": budget.filter_transmission_at_laser,
        },
        "metrics": {
            "estimated_range_m": estimated_range,
            "bias_cm": bias_cm,
            "precision_cm_1sigma": precision_cm,
            "success_rate": success_rate,
            "observed_peak_snr": peak_snr,
            "recorded_counts": float(observed.sum()),
            "expected_noise_counts": float(expected_noise.sum()),
            "pileup_loss_fraction": float(
                max(0.0, 1.0 - expected.sum() / max((budget.signal_detected_per_pulse + budget.background_detected_per_gate + budget.dark_detected_per_gate + budget.other_detected_per_gate) * cfg.laser_shots, 1e-30))
            ),
            "trials_completed": int(estimates.size),
        },
        "histogram": {
            "time_ns": time_ns.tolist(),
            "expected_counts": expected.tolist(),
            "expected_noise_counts": expected_noise.tolist(),
            "observed_counts": observed.tolist(),
        },
        "range_sweep": _range_sweep(cfg),
        "crosstalk": {
            "direct_matrix": direct_xt.tolist(),
            "total_induced_matrix": total_xt.tolist(),
            "source_channel": source,
            "victim_profile": victim_profile.tolist(),
            "total_induced_fraction": float(victim_profile.sum()),
        },
    }


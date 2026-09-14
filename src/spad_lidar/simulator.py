from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import pi, sqrt

import numpy as np
from scipy.special import ndtr
from scipy.signal import convolve

from .constants import C, H, FWHM_TO_SIGMA
from .configuration import Algorithms, read_yaml
from .models import SimulationConfig
from .filters import FilterResponse
from .spectra import spectral_components
from .readout import event_acquisition


@dataclass(frozen=True)
class Budget:
    signal_detected_per_pulse: float
    background_detected_per_gate: float
    dark_detected_per_gate: float
    other_detected_per_gate: float
    filter_enbw_nm: float
    filter_transmission_at_laser: float
    photon_energy_j: float
    aperture_area_m2: float
    received_signal_j: float
    background_power_w: float
    effective_pdp: float
    channel_solid_angle_sr: float
    emitted_energy_j: float
    geometric_collection: float
    solar_detected_per_gate: float
    other_light_detected_per_gate: float
    solar_background_power_w: float
    other_light_background_power_w: float
    pde_at_laser: float


def aperture_area(cfg: SimulationConfig) -> float:
    """Projected clear entrance pupil area; ellipse sizes are FULL axes."""
    if cfg.rx_aperture_shape == "circle":
        return pi * (cfg.rx_aperture_mm * 1e-3 / 2) ** 2
    area = cfg.rx_aperture_width_mm * cfg.rx_aperture_height_mm * 1e-6
    return area * pi / 4 if cfg.rx_aperture_shape == "ellipse" else area


def timing_sigma_ns(cfg):
    laser_sigma = cfg.pulse_fwhm_ps / (
        FWHM_TO_SIGMA if cfg.pulse_shape == "gaussian" else sqrt(12)
    )
    return sqrt(laser_sigma**2 + (cfg.spad_jitter_fwhm_ps / FWHM_TO_SIGMA)**2
                + (cfg.other_jitter_fwhm_ps / FWHM_TO_SIGMA)**2) * 1e-3


def derived_quantities(cfg, algorithms=None):
    a = algorithms or Algorithms.load()
    width_s = cfg.pulse_fwhm_ps * 1e-12
    energy_j = cfg.pulse_energy_nj * 1e-9
    shape_factor = sqrt(pi / (4 * np.log(2))) if cfg.pulse_shape == "gaussian" else 1.0
    peak_w = energy_j / (width_s * shape_factor)
    time_ps = np.linspace(-a.pulse_preview_half_widths * cfg.pulse_fwhm_ps,
                          a.pulse_preview_half_widths * cfg.pulse_fwhm_ps,
                          a.pulse_preview_points)
    if cfg.pulse_shape == "gaussian":
        shape = np.exp(-4 * np.log(2) * (time_ps / cfg.pulse_fwhm_ps)**2)
    else:
        shape = (np.abs(time_ps) <= cfg.pulse_fwhm_ps / 2).astype(float)
    return {
        "peak_power_w": float(peak_w),
        "average_power_w": energy_j * cfg.laser_prf_hz,
        "tx_output_peak_power_w": float(peak_w * cfg.tx_efficiency),
        "tx_output_average_power_w": energy_j * cfg.laser_prf_hz * cfg.tx_efficiency,
        "pulse_integral_factor": float(shape_factor),
        "repetition_period_ns": 1e9 / cfg.laser_prf_hz,
        "acquisition_time_ms": cfg.laser_shots / cfg.laser_prf_hz * 1e3,
        "aperture_area_mm2": aperture_area(cfg) * 1e6,
        "tof_ns": 2 * cfg.range_m / C * 1e9 + cfg.calibration_delay_ns,
        "irf_sigma_ns": timing_sigma_ns(cfg),
        "range_bin_m": C * cfg.tdc_bin_ps * 1e-12 / 2,
        "pulse": {"time_ps": time_ps.tolist(), "power_w": (shape * peak_w).tolist()},
        "filter": filter_profile(cfg, a),
        "spectra": spectral_components(cfg, a, plot=True),
    }


def _filter_properties(cfg):
    response = FilterResponse(cfg)
    return response.integral_nm(), response.evaluate(cfg.wavelength_nm)


def filter_profile(cfg, algorithms=None):
    a = algorithms or Algorithms.load()
    response = FilterResponse(cfg)
    wl, tr = response.wavelength, response.transmission
    lower, upper = min(wl[0], cfg.wavelength_nm), max(wl[-1], cfg.wavelength_nm)
    padding = (upper-lower)*a.filter_plot_padding_fraction
    enbw, transmission = response.integral_nm(), response.evaluate(cfg.wavelength_nm)
    # Always include the original knots as well as a dense plotting grid.
    plot_wl = np.unique(np.r_[np.linspace(wl[0], wl[-1], a.filter_plot_samples), response.plot_knots(a)])
    plot_tr = response.evaluate(plot_wl)
    return {
        "source": "csv_curve" if response.has_samples else "basic_filter",
        "input_mode": cfg.spectral_inputs.filter.mode,
        "basic_shape": cfg.spectral_inputs.filter.basic.shape,
        "interpolation": "rectangular" if response.method=="rectangle" else response.method,
        "original_wavelength_nm": wl.tolist() if response.has_samples else [],
        "original_transmission": tr.tolist() if response.has_samples else [],
        "wavelength_nm": [max(0.0, lower-padding), float(wl[0]), *plot_wl.tolist(), float(wl[-1]), upper+padding],
        "transmission": [0.0, 0.0, *plot_tr.tolist(), 0.0, 0.0],
        "polynomial_coefficients": response.polynomial.c.tolist() if response.polynomial is not None else None,
        "laser_wavelength_nm": cfg.wavelength_nm,
        "laser_transmission": transmission,
        "weighted_bandwidth_nm": enbw,
        "support_nm": [float(wl[0]), float(wl[-1])],
        "note": "原始点为散点；曲线按选定方式插值，区间外为0。激光透过率和背景积分使用同一插值函数；PCHIP积分为分段多项式解析积分，不受绘图采样密度影响。系数按SciPy PPoly约定，以各左端点为原点，降幂排列。",
    }


def photon_budget(cfg: SimulationConfig, range_m=None) -> Budget:
    r = cfg.range_m if range_m is None else range_m
    photon_energy = H * C / (cfg.wavelength_nm * 1e-9)
    area = aperture_area(cfg)
    enbw, transmission = _filter_properties(cfg)
    # Input reference plane is BEFORE Tx optics, for this angular channel.
    energy = cfg.pulse_energy_nj * 1e-9
    geometry = area / (pi * r**2)
    received = (energy * cfg.tx_efficiency * cfg.target_reflectivity * geometry
                * cfg.rx_efficiency * transmission * cfg.overlap_factor
                * cfg.atmospheric_one_way_transmission**2)
    spectral = spectral_components(cfg)
    effective_pdp = spectral["pde_at_laser"] * cfg.fill_factor
    omega = cfg.channel_ifov_h_mrad * cfg.channel_ifov_v_mrad * 1e-6
    geometry_bg = area*omega*cfg.rx_efficiency
    solar_power = spectral["solar_filtered_radiance_w_m2_sr"]*geometry_bg
    other_power = spectral["other_filtered_radiance_w_m2_sr"]*geometry_bg
    background_power = solar_power+other_power
    gate_s = cfg.gate_width_ns * 1e-9
    solar_counts = spectral["solar_detectable_photons_s_m2_sr"]*geometry_bg*cfg.fill_factor*gate_s
    other_counts = spectral["other_detectable_photons_s_m2_sr"]*geometry_bg*cfg.fill_factor*gate_s
    return Budget(
        received / photon_energy * effective_pdp,
        solar_counts+other_counts,
        cfg.dcr_cps_per_spad * cfg.spads_per_channel * gate_s,
        cfg.other_noise_cps_per_spad * cfg.spads_per_channel * gate_s,
        enbw, transmission, photon_energy, area, received, background_power,
        effective_pdp, omega, energy, geometry, solar_counts, other_counts,
        solar_power, other_power, spectral["pde_at_laser"],
    )


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


def _first_photon_probabilities(mu):
    before = np.r_[0.0, np.cumsum(mu[:-1])]
    return np.exp(-before) * (-np.expm1(-mu))


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


def _sample_histogram(rng, expected, opportunities):
    p = np.maximum(expected / opportunities, 0)
    # Numerical guard at floating point saturation, not a configuration fallback.
    p = np.r_[p, max(0.0, 1-float(p.sum()))]
    p /= p.sum()
    return rng.multinomial(opportunities, p)[:-1].astype(float)


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


def simulate(cfg: SimulationConfig, debug=False) -> dict:
    a = Algorithms.load()
    x = _histogram_components(cfg)
    b = x["budget"]
    derived = derived_quantities(cfg, a)
    rng = np.random.default_rng(cfg.rng_seed)
    opportunities = cfg.laser_shots * cfg.spads_per_channel
    if cfg.readout_mode == 'analytic_reference':
        observed = _sample_histogram(rng, x["expected"], opportunities)
        trials = [_sample_histogram(rng, x['expected'], opportunities) for _ in range(cfg.monte_carlo_trials)]
        readout = {'mode':cfg.readout_mode,'engine':'analytic_multinomial','note':'Ideal reset each cycle; finite dead times and limits not used.'}
    else:
        observed, x['expected'], x['expected_noise'], trials, readout = event_acquisition(cfg,b,a,x['edges'])
    estimate, score, estimator = _estimate_range(cfg, x["time"], observed, a, with_trace=True)
    estimates = [_estimate_range(cfg, x['time'], h, a)[0] for h in trials]
    valid = np.array([r for r in estimates if r is not None])
    errors = valid-cfg.range_m
    successes = sum(r is not None and abs(r-cfg.range_m) <= a.success_tolerance_m for r in estimates)
    source = cfg.line_channels // 2
    # Legacy multi-channel diagnostics must not block the A single-channel chain.
    try:
        direct, total = crosstalk_model(cfg)
        crosstalk = {
            "status": "ok", "direct_matrix": direct.tolist(),
            "total_induced_matrix": total.tolist(), "source_channel": source,
            "victim_profile": total[:,source].tolist(),
            "total_induced_fraction": float(total[:,source].sum()),
            "spectral_radius": float(np.max(np.abs(np.linalg.eigvalsh(direct)))),
        }
    except ValueError as exc:
        crosstalk = {"status": "invalid", "error": str(exc), "source_channel": source}
    ideal_in_gate = float((x["mu_signal"]+x["mu_noise"]).sum()*opportunities)
    config_snapshot = {"simulation": cfg.model_dump(), "algorithms": a.model_dump()}
    fingerprint = sha256(json.dumps(config_snapshot, sort_keys=True).encode()).hexdigest()
    result = {
        "configuration": config_snapshot,
        "provenance": {"model_version": "0.1.5", "simulation_scope": "A_single_angular_channel", "utc": datetime.now(timezone.utc).isoformat(),
                       "sha256": fingerprint, "defaults_source": "config/defaults.yaml"},
        "derived": derived,
        "readout": readout,
        "assumptions": [
            "输入脉冲能量是当前角通道在 Tx 光学之前的能量；显示功率也以此为参考面。",
            "正入射大朗伯面、小接收立体角；通道信号均匀分配到所选 SPAD，无真实二维 PSF。",
            "读出模式："+read_yaml('readout-modes.yaml')[cfg.readout_mode]['description'],
            "太阳光按标准谱形由lux归一化后经灰朗伯面反射；其他环境光与PDE按谱线联合积分，时间上均匀。",
            "事件模式使用非延长型SPAD/TDC死时间；显示曲线为多次MC均值。解析参考才使用首光子多项分布。",
            "串扰矩阵独立分析，未耦合到直方图；尚未包含afterpulse、雪崩串扰、扫描运动与系统漂移。",
            "距离扫描曲线是无 pile-up 的理想预算；峰值评分不是虚警率标定后的检测 SNR。",
            "成功率=误差在所配置容差内的次数/请求重复次数；精度和偏差仅统计能输出距离的重复。",
        ],
        "budget": asdict(b),
        "metrics": {
            "estimated_range_m": estimate,
            "bias_cm": float(errors.mean()*100) if len(valid) else None,
            "precision_cm_1sigma": float(valid.std(ddof=1)*100) if len(valid)>1 else None,
            "success_rate": successes/cfg.monte_carlo_trials if cfg.monte_carlo_trials else None,
            "success_tolerance_m": a.success_tolerance_m,
            "observed_peak_snr": score,
            "recorded_counts": int(observed.sum()),
            "expected_noise_counts": float(x["expected_noise"].sum()),
            "pileup_loss_fraction": max(0, 1-float(x["expected"].sum())/ideal_in_gate) if ideal_in_gate else 0,
            "trials_completed": cfg.monte_carlo_trials, "valid_trials": len(valid),
        },
        "histogram": {
            "time_ns": x["time"].tolist(), "edges_ns": x["edges"].tolist(),
            "expected_counts": x["expected"].tolist(), "expected_noise_counts": x["expected_noise"].tolist(),
            "observed_counts": observed.tolist(),
        },
        "range_sweep": _range_sweep(cfg, a),
        "crosstalk": crosstalk,
    }
    if debug:
        result["debug"] = {
            "parameter_help": read_yaml("parameter-help.yaml"),
            "formulas": read_yaml("formulas.yaml"),
            "formula_notes": read_yaml("formula-notes.yaml"),
            "spectral_audit": derived['spectra'],
            "readout_audit": readout,
            "bin_reference_note": "概率列仅为理想首光子参考；事件模式实际结果由readout_audit和观测直方图描述。",
            "constants": {"c_m_per_s": C, "h_j_s": H, "fwhm_to_sigma": FWHM_TO_SIGMA},
            "steps": [
                {"title": "1. 脉冲能量与功率（Tx 前）",
                 "formula_id": "power",
                 "values": {k:v for k,v in derived.items() if k not in ("pulse", "filter", "spectra")}},
                {"title": "2. 接收孔径与信号能量",
                 "formula_id": "signal",
                 "values": {"area_m2": b.aperture_area_m2, "geometric_collection": b.geometric_collection,
                            "emitted_j": b.emitted_energy_j, "received_j": b.received_signal_j}},
                {"title": "3. 光子预算与背景",
                 "formula_id": "spectral",
                 "values": asdict(b)},
                {"title": "4. 门控与首光子竞争",
                 "formula_id": "reference",
                 "values": {"captured_signal_fraction": float(x["shape"].sum()),
                            "signal_counts_before_pileup": float(x["mu_signal"].sum()*opportunities),
                            "ideal_total_counts_in_gate": ideal_in_gate,
                            "expected_recorded_counts": float(x["expected"].sum()),
                            "no_event_probability_per_spad_shot": x["no_event_probability"],
                            "probability_sum_with_no_event": float(x["probability"].sum()+x["no_event_probability"]),
                            "opportunities": opportunities}},
                {"title": "5. 随机观测和测距",
                 "formula_id": "estimate",
                 "values": {k:v for k,v in estimator.items() if not isinstance(v,list)}},
                {"title": "6. 重复实验统计",
                 "formula_id": "statistics",
                 "values": result["metrics"]},
                {"title": "7. 独立串扰分析",
                 "formula_id": "crosstalk",
                 "values": {"status": crosstalk["status"], "error": crosstalk.get("error"),
                            "spectral_radius": crosstalk.get("spectral_radius"),
                            "source_channel": source, "induced_fraction": crosstalk.get("total_induced_fraction"),
                            "coupled_into_histogram": False}},
            ],
            "bins": {
                "signal_fraction": x["shape"].tolist(),
                "mu_signal_per_spad": x["mu_signal"].tolist(),
                "mu_noise_per_spad": x["mu_noise"].tolist(),
                "survival_before_bin": x["survival"].tolist(),
                "first_event_probability": x["probability"].tolist(),
            },
            "estimator": estimator,
            "trial_estimates_m": estimates,
            "trial_errors_m": [r-cfg.range_m if r is not None else None for r in estimates],
        }
    return result

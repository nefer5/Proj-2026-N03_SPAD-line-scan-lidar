"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from ..configuration import Algorithms, read_yaml
from ..models import SimulationConfig
from ..readout import event_acquisition, event_histogram
from ..detection import evaluate_detection
from ..reporting.a_view import derived_quantities, signal_ground_truth
from .a_signal import _histogram_components
from .legacy_diagnostics import crosstalk_model, _range_sweep
from ..spad.analytical import _sample_histogram
from ..processing.ranging import _estimate_range
from ..processing.statistics import histogram_sample_range


def simulate(cfg: SimulationConfig, debug=False) -> dict:
    a = Algorithms.load()
    x = _histogram_components(cfg)
    b = x["budget"]
    derived = derived_quantities(cfg, a)
    rng = np.random.default_rng(cfg.rng_seed)
    opportunities = cfg.laser_shots * cfg.spads_per_channel
    ground_truth=signal_ground_truth(cfg,b,x['edges'],a)
    if cfg.detection_enabled and len(x['time'])*(a.detector_calibration_trials+a.detector_null_trials+cfg.monte_carlo_trials+1)>a.max_detection_bin_work:
        raise ValueError('Detection histogram work exceeds max_detection_bin_work; reduce bins or repetitions')
    if cfg.readout_mode == 'analytic_reference':
        observed = _sample_histogram(rng, x["expected"], opportunities)
        trials = ([observed.copy()]+[_sample_histogram(rng, x['expected'], opportunities)
                                    for _ in range(cfg.monte_carlo_trials-1)]) if cfg.monte_carlo_trials else []
        readout = {'mode':cfg.readout_mode,'engine':'analytic_multinomial','note':'Ideal reset each cycle; finite dead times and limits not used.'}
    else:
        observed, x['expected'], x['expected_noise'], trials, readout = event_acquisition(cfg,b,a,x['edges'])
    estimate, score, estimator = _estimate_range(cfg, x["time"], observed, a, with_trace=True)
    estimates = [_estimate_range(cfg, x['time'], h, a)[0] for h in trials]
    raw_estimate=estimate
    raw_estimates=list(estimates)
    detection={'enabled':False,'note':'Legacy unthresholded peak search; no calibrated Pd/PFA.'}
    if cfg.detection_enabled:
        noise_sampler=(lambda generator:_sample_histogram(generator,x['expected_noise'],opportunities)) if cfg.readout_mode=='analytic_reference' else (lambda generator:event_histogram(cfg,b,generator,a,x['edges'],signal=False)[0])
        detection=evaluate_detection(cfg,a,observed,trials,noise_sampler,
                                     lambda hist:_estimate_range(cfg,x['time'],hist,a),b.signal_detected_per_pulse>0)
        estimate=detection['observed']['distance_m']
        estimates=detection['accepted_trial_estimates_m']
    estimator['distance_is_raw_before_threshold']=True
    estimator['accepted_distance_m']=estimate
    estimator['detection_enabled']=cfg.detection_enabled
    sample_range=histogram_sample_range(trials)
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
        "provenance": {"model_version": "0.2.1", "simulation_scope": "A_single_angular_channel", "utc": datetime.now(timezone.utc).isoformat(),
                       "sha256": fingerprint, "defaults_source": "config/defaults.yaml"},
        "derived": derived,
        "readout": readout,
        "detection":detection,
        "assumptions": [
            "输入脉冲能量是当前角通道在 Tx 光学之前的能量；显示功率也以此为参考面。",
            "正入射大朗伯面、小接收立体角；通道信号均匀分配到所选 SPAD，无真实二维 PSF。",
            "读出模式："+read_yaml('readout-modes.yaml')[cfg.readout_mode]['description'],
            "太阳光按标准谱形由lux归一化后经灰朗伯面反射；其他环境光与PDE按谱线联合积分，时间上均匀。",
            "青色ground truth为纯信号解析参考，不含读出损失；观测含噪声和读出限制，事件模式橙色噪声线为MC均值。",
            "串扰矩阵独立分析，未耦合到直方图；尚未包含afterpulse、雪崩串扰、扫描运动与系统漂移。",
            "距离扫描曲线是无 pile-up 的理想预算；峰值评分不是虚警率标定后的检测 SNR。",
            "成功率=误差在所配置容差内的次数/请求重复次数；精度和偏差仅统计能输出距离的重复。",
        ],
        "budget": asdict(b),
        "metrics": {
            "raw_estimated_range_m":raw_estimate,
            "detection_status":('detected' if estimate is not None else 'not_detected') if cfg.detection_enabled else 'threshold_disabled',
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
            "sample_range":sample_range,
            "ground_truth":ground_truth,
            "expected_counts_note":"含信号和噪声、经过所选读出的均值，仅用于诊断；不是青色ground truth。",
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
                 "values": {k:v for k,v in derived.items() if k not in ("pulse", "filter", "spectra", "photon_flow", "binning")}},
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
            "raw_trial_estimates_m":raw_estimates,
            "trial_errors_m": [r-cfg.range_m if r is not None else None for r in estimates],
        }
    return result


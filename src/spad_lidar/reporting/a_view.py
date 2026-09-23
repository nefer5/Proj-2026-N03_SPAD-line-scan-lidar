"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from ..configuration import Algorithms
from ..spectra import spectral_components
from ..rx.budget import photon_budget, aperture_area
from ..filters import FilterResponse
from ..photon_flow import build_photon_flow
from ..experiments.a_signal import timing_sigma_ns, _signal_shape, _signal_pdf, _time_axis, _preview_edges


def derived_quantities(cfg, algorithms=None):
    a = algorithms or Algorithms.load()
    spectral=spectral_components(cfg,a,plot=True)
    budget=photon_budget(cfg,spectral=spectral)
    gate_fraction=float(_signal_shape(cfg,_time_axis(cfg)[0]).sum())
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
        "binning": {"H_binning":cfg.H_binning,"V_binning":cfg.V_binning,"spads_per_channel":cfg.spads_per_channel},
        "pulse": {"time_ps": time_ps.tolist(), "power_w": (shape * peak_w).tolist()},
        "filter": filter_profile(cfg, a),
        "spectra": spectral,
        "photon_flow": build_photon_flow(cfg,budget,spectral,gate_fraction),
    }


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


def signal_ground_truth(cfg, budget, edges, algorithms):
    fine_edges,factor=_preview_edges(edges,algorithms)
    amplitude=cfg.laser_shots*budget.signal_detected_per_pulse
    shape=_signal_shape(cfg,edges)
    tof=2*cfg.range_m/C*1e9+cfg.calibration_delay_ns
    extent=algorithms.ground_truth_extent_sigma*timing_sigma_ns(cfg)
    local=np.linspace(max(edges[0],tof-extent),min(edges[-1],tof+extent),algorithms.ground_truth_plot_points)
    # Include pulse discontinuities at adjacent floating-point positions, so an
    # unjittered rectangular waveform is not rendered with sloping shoulders.
    features=np.array([tof-cfg.pulse_fwhm_ps*1e-3/2,tof,tof+cfg.pulse_fwhm_ps*1e-3/2])
    grid=np.unique(np.r_[(fine_edges[:-1]+fine_edges[1:])/2,local,edges[0],edges[-1],
                         features,np.nextafter(features,-np.inf),np.nextafter(features,np.inf)])
    grid=grid[(grid>=edges[0]) & (grid<=edges[-1])]
    density=amplitude*_signal_pdf(cfg,grid)
    return {
        'basis':'pure_signal_analytic_before_readout',
        'reference_plane':'after_PDE_FF_before_SPAD_dead_time_and_readout',
        'counts':(amplitude*shape).tolist(),
        'sensor_incident_counts':(cfg.laser_shots*budget.signal_sensor_incident_photons_per_pulse*shape).tolist(),
        'in_gate_total':float(amplitude*shape.sum()),
        'full_signal_total':float(amplitude),
        'high_resolution':{
            'time_ns':grid.tolist(),
            'counts_per_ns':density.tolist(),
            'counts_per_nominal_bin':(density*cfg.tdc_bin_ps*1e-3).tolist(),
            'edges_ns':fine_edges.tolist(),
            'integrated_counts':(amplitude*_signal_shape(cfg,fine_edges)).tolist(),
            'nominal_bin_width_ns':cfg.tdc_bin_ps*1e-3,
            'subdivisions':factor,
        },
        'note':'青色为纯信号解析ground truth：PDE/FF后的理想候选计数，含已配置脉宽和抖动分布的解析展宽；不含背景、暗计数、随机抽样、死时间、首事件竞争或读出容量损失。散点为当前bin积分；虚线为解析计数密度×标称bin宽，不必穿过积分散点。与24次均值和测距重复次数均无关。',
    }


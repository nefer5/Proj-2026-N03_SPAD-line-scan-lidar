"""Spectral backgrounds and PDE, with traceable photopic solar normalization."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import io
import zipfile

import numpy as np
from .curves import Curve

from .constants import C, H, K_PHOTOPIC
from .configuration import read_yaml, Algorithms, ConfigurationError
from .filters import FilterResponse

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def reference_data():
    manifest = read_yaml("spectral-data.yaml")
    arrays = []
    for key in ("solar", "photopic"):
        info = manifest[key]
        data = (ROOT / info["path"]).read_bytes()
        if sha256(data).hexdigest() != info["sha256"]:
            raise ConfigurationError(f"Reference data checksum mismatch: {key}")
        if key == "solar":
            data = zipfile.ZipFile(io.BytesIO(data)).read(info["member"])
        arrays.append(np.loadtxt(io.BytesIO(data), delimiter=",", skiprows=info["skiprows"]))
    return arrays[0], arrays[1], manifest


def quadrature(knots, order):
    knots = np.unique(knots)
    nodes, weights = np.polynomial.legendre.leggauss(order)
    half = np.diff(knots)/2
    x = (knots[:-1,None]+knots[1:,None])/2 + half[:,None]*nodes
    w = half[:,None]*weights
    return x.ravel(), w.ravel()


@lru_cache(maxsize=8)
def solar_normalization(order):
    solar, photopic, _ = reference_data()
    knots = np.unique(np.r_[solar[:,0], photopic[:,0]])
    x,w = quadrature(knots,order)
    irradiance = np.interp(x,solar[:,0],solar[:,2],left=0,right=0)
    vision = np.interp(x,photopic[:,0],photopic[:,1],left=0,right=0)
    return float(K_PHOTOPIC*np.dot(w,irradiance*vision)), float(np.dot(w,irradiance))


def spectral_components(cfg, algorithms=None, plot=False):
    a = algorithms or Algorithms.load()
    solar, _, manifest = reference_data()
    solar_custom = None if cfg.spectral_inputs.solar.mode=="standard" else Curve(cfg.spectral_inputs.solar)
    other = Curve(cfg.spectral_inputs.other)
    pde = Curve(cfg.spectral_inputs.pde)
    filt = FilterResponse(cfg)
    if solar_custom is None:
        reference_lux, reference_w_m2 = solar_normalization(a.spectral_quadrature_order)
        solar_knots=solar[:,0]
    else:
        solar_knots=solar_custom.knots(a)
        _, photopic, _ = reference_data()
        k=np.unique(np.r_[solar_knots,photopic[:,0]])
        xx,ww=quadrature(k,a.spectral_quadrature_order)
        values=solar_custom(xx)
        vision=np.interp(xx,photopic[:,0],photopic[:,1],left=0,right=0)
        reference_lux=float(K_PHOTOPIC*np.dot(ww,values*vision))
        reference_w_m2=solar_custom.integral_nm()
    if cfg.solar_enabled and cfg.solar_illuminance_lux>0 and reference_lux<=0:
        raise ValueError("Selected solar shape has no visible photopic energy; cannot normalize positive lux")
    scale=cfg.solar_illuminance_lux/reference_lux if cfg.solar_enabled and reference_lux>0 else 0.0

    def solar_e(x):
        values=solar_custom(x) if solar_custom is not None else np.interp(x,solar[:,0],solar[:,2],left=0,right=0)
        return scale*values

    def other_l(x):
        return other(x)*cfg.other_light_scale if cfg.other_light_enabled else np.zeros_like(x)

    def pde_at(x):
        return pde(x)

    # Split at every interpolation knot and basic-waveform feature. Polynomial
    # products are integrated exactly by order 6; Gaussian/cosine shapes receive
    # local refinement from Curve.knots, independently of plot sampling density.
    knots = np.unique(np.r_[filt.knots(a), solar_knots, other.knots(a), pde.knots(a)])
    knots = knots[(knots>=filt.wavelength[0]) & (knots<=filt.wavelength[-1])]
    x,w = quadrature(knots,a.spectral_quadrature_order)
    sun_l = solar_e(x)*cfg.solar_reflectivity/np.pi
    ambient_l = other_l(x)
    t = filt.evaluate(x)
    detector_weight = t*pde_at(x)*x*1e-9/(H*C)
    photon_factor=x*1e-9/(H*C)
    result = {
        "solar_lux": cfg.solar_illuminance_lux if cfg.solar_enabled else 0.0,
        "solar_reference_lux": reference_lux,
        "solar_irradiance_w_m2": scale*reference_w_m2,
        "solar_scale": scale,
        "solar_reference_irradiance_w_m2": reference_w_m2,
        "budget_band_nm": [float(filt.wavelength[0]),float(filt.wavelength[-1])],
        "solar_irradiance_at_laser_w_m2_nm": float(solar_e(np.array(cfg.wavelength_nm))),
        "solar_radiance_at_laser_w_m2_sr_nm": float(solar_e(np.array(cfg.wavelength_nm))*cfg.solar_reflectivity/np.pi),
        "other_raw_radiance_at_laser_w_m2_sr_nm": float(other(np.array(cfg.wavelength_nm))),
        "other_radiance_at_laser_w_m2_sr_nm": float(other_l(np.array(cfg.wavelength_nm))),
        "pde_at_laser": float(pde_at(np.array(cfg.wavelength_nm))),
        "solar_filtered_radiance_w_m2_sr": float(np.dot(w,sun_l*t)),
        "other_filtered_radiance_w_m2_sr": float(np.dot(w,ambient_l*t)),
        "solar_incident_radiance_w_m2_sr": float(np.dot(w,sun_l)),
        "other_incident_radiance_w_m2_sr": float(np.dot(w,ambient_l)),
        "solar_incident_photons_s_m2_sr": float(np.dot(w,sun_l*photon_factor)),
        "other_incident_photons_s_m2_sr": float(np.dot(w,ambient_l*photon_factor)),
        "solar_filtered_photons_s_m2_sr": float(np.dot(w,sun_l*t*photon_factor)),
        "other_filtered_photons_s_m2_sr": float(np.dot(w,ambient_l*t*photon_factor)),
        "solar_detectable_photons_s_m2_sr": float(np.dot(w,sun_l*detector_weight)),
        "other_detectable_photons_s_m2_sr": float(np.dot(w,ambient_l*detector_weight)),
        "standard": manifest["solar"]["name"] if solar_custom is None else "Custom solar spectral shape",
        "input_modes": {key:getattr(cfg.spectral_inputs,key).mode for key in ("filter","solar","other","pde")},
        "source_checksums": {k:manifest[k]["sha256"] for k in ("solar","photopic")},
        "notes": [
            "太阳lux表示目标面照度，按所选标准/自定义谱形归一化。自定义幅值仅影响归一化前参考量，不独立决定归一化后强度。",
            "太阳背景为灰朗伯面反射：太阳谱辐照度乘solar_reflectivity/π。不是太阳直视模型。",
            "其他环境光输入为接收方向谱辐亮度，不再乘反射率；示例不是实测光源。",
            "PDE为感光区探测概率，未包含fill factor；示例曲线不是器件规格。输入已含FF时将FF设为1。",
            "用户光谱/PDE采样范围外为0；标准太阳表的线间细节受原始采样限制。",
        ],
    }
    if plot:
        lower=min(a.spectral_plot_min_nm,other.x[0],pde.x[0],cfg.wavelength_nm,solar_custom.x[0] if solar_custom is not None else a.spectral_plot_min_nm)
        upper=max(a.spectral_plot_max_nm,other.x[-1],pde.x[-1],cfg.wavelength_nm,solar_custom.x[-1] if solar_custom is not None else a.spectral_plot_max_nm)
        dense=np.linspace(lower,upper,a.spectral_plot_samples)
        grid=np.unique(np.r_[dense,solar_knots[(solar_knots>=lower)&(solar_knots<=upper)],other.plot_knots(a),pde.plot_knots(a),solar_custom.plot_knots(a) if solar_custom else [],cfg.wavelength_nm])
        sun_scene=solar_e(grid)*cfg.solar_reflectivity/np.pi
        other_scene=other_l(grid)
        result["curves"] = {
            "wavelength_nm": grid.tolist(), "solar_irradiance": solar_e(grid).tolist(),
            "solar_original_x": solar_custom.x.tolist() if solar_custom and solar_custom.has_samples else [],
            "solar_original_y": (solar_custom.y*scale).tolist() if solar_custom and solar_custom.has_samples else [],
            "solar_radiance": sun_scene.tolist(), "other_radiance": other_scene.tolist(),
            "total_radiance": (sun_scene+other_scene).tolist(), "pde": pde_at(grid).tolist(),
            "other_original_x": other.x.tolist() if other.has_samples else [],
            "other_original_y": (other.y*cfg.other_light_scale*cfg.other_light_enabled).tolist() if other.has_samples else [],
            "pde_original_x": pde.x.tolist() if pde.has_samples else [],
            "pde_original_y": pde.y.tolist() if pde.has_samples else [],
        }
        result["integration"] = {
            "wavelength_nm":x.tolist(),"weights_nm":w.tolist(),
            "solar_radiance":sun_l.tolist(),"other_radiance":ambient_l.tolist(),
            "filter_transmission":t.tolist(),"pde":pde_at(x).tolist(),
            "detector_weight":detector_weight.tolist(),
            "photon_factor_per_joule":photon_factor.tolist(),
        }
    return result

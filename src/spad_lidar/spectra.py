"""Spectral backgrounds and PDE, with traceable photopic solar normalization."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import io
import zipfile

import numpy as np
from scipy.interpolate import PchipInterpolator

from .constants import C, H, K_PHOTOPIC
from .configuration import read_yaml, Algorithms, ConfigurationError
from .filters import FilterResponse

ROOT = Path(__file__).resolve().parents[2]


class SampledSpectrum:
    def __init__(self, points, value_key, method):
        self.x = np.array([p.wavelength_nm for p in points])
        self.y = np.array([getattr(p, value_key) for p in points])
        self.poly = PchipInterpolator(self.x, self.y, extrapolate=False) if method == "pchip" else None

    def __call__(self, x):
        x = np.asarray(x)
        values = self.poly(x) if self.poly is not None else np.interp(x, self.x, self.y)
        return np.where((x >= self.x[0]) & (x <= self.x[-1]), values, 0.0)


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
    reference_lux, reference_w_m2 = solar_normalization(a.spectral_quadrature_order)
    scale = cfg.solar_illuminance_lux/reference_lux if cfg.solar_enabled else 0.0
    other = SampledSpectrum(cfg.other_light_spectrum,"radiance",cfg.other_light_interpolation)
    pde = SampledSpectrum(cfg.pde_spectrum,"pde",cfg.pde_interpolation)
    filt = FilterResponse(cfg)

    def solar_e(x):
        return scale*np.interp(x,solar[:,0],solar[:,2],left=0,right=0)

    def other_l(x):
        values = other(x) if cfg.other_light_mode == "spectrum" else np.full_like(x,cfg.background_spectral_radiance,dtype=float)
        return values*cfg.other_light_scale if cfg.other_light_enabled else np.zeros_like(x)

    def pde_at(x):
        return pde(x) if cfg.pde_mode == "spectrum" else np.full_like(x,cfg.pde,dtype=float)

    # Split at every knot: Gauss order 6 integrates products of piecewise cubic
    # spectra, filter, PDE and wavelength (polynomial degree <=10) exactly.
    knots = np.unique(np.r_[filt.wavelength, solar[:,0], other.x, pde.x])
    knots = knots[(knots>=filt.wavelength[0]) & (knots<=filt.wavelength[-1])]
    x,w = quadrature(knots,a.spectral_quadrature_order)
    sun_l = solar_e(x)*cfg.solar_reflectivity/np.pi
    ambient_l = other_l(x)
    t = filt.evaluate(x)
    detector_weight = t*pde_at(x)*x*1e-9/(H*C)
    result = {
        "solar_lux": cfg.solar_illuminance_lux if cfg.solar_enabled else 0.0,
        "solar_reference_lux": reference_lux,
        "solar_irradiance_w_m2": scale*reference_w_m2,
        "solar_scale": scale,
        "pde_at_laser": float(pde_at(np.array(cfg.wavelength_nm))),
        "solar_filtered_radiance_w_m2_sr": float(np.dot(w,sun_l*t)),
        "other_filtered_radiance_w_m2_sr": float(np.dot(w,ambient_l*t)),
        "solar_detectable_photons_s_m2_sr": float(np.dot(w,sun_l*detector_weight)),
        "other_detectable_photons_s_m2_sr": float(np.dot(w,ambient_l*detector_weight)),
        "standard": manifest["solar"]["name"],
        "source_checksums": {k:manifest[k]["sha256"] for k in ("solar","photopic")},
        "notes": [
            "太阳lux表示目标面照度，以固定AM1.5G谱形缩放；不是任意光源lux到近红外的通用换算。",
            "太阳背景为灰朗伯面反射：太阳谱辐照度乘solar_reflectivity/π。不是太阳直视模型。",
            "其他环境光输入为接收方向谱辐亮度，不再乘反射率；示例不是实测光源。",
            "PDE为感光区探测概率，未包含fill factor；示例曲线不是器件规格。输入已含FF时将FF设为1。",
            "用户光谱/PDE采样范围外为0；标准太阳表的线间细节受原始采样限制。",
        ],
    }
    if plot:
        lower=min(a.spectral_plot_min_nm,other.x[0],pde.x[0],cfg.wavelength_nm)
        upper=max(a.spectral_plot_max_nm,other.x[-1],pde.x[-1],cfg.wavelength_nm)
        dense=np.linspace(lower,upper,a.spectral_plot_samples)
        grid=np.unique(np.r_[dense,solar[(solar[:,0]>=lower)&(solar[:,0]<=upper),0],other.x,pde.x,cfg.wavelength_nm])
        sun_scene=solar_e(grid)*cfg.solar_reflectivity/np.pi
        other_scene=other_l(grid)
        result["curves"] = {
            "wavelength_nm": grid.tolist(), "solar_irradiance": solar_e(grid).tolist(),
            "solar_radiance": sun_scene.tolist(), "other_radiance": other_scene.tolist(),
            "total_radiance": (sun_scene+other_scene).tolist(), "pde": pde_at(grid).tolist(),
            "other_original_x": other.x.tolist() if cfg.other_light_mode=="spectrum" else [],
            "other_original_y": (other.y*cfg.other_light_scale*cfg.other_light_enabled).tolist() if cfg.other_light_mode=="spectrum" else [],
            "pde_original_x": pde.x.tolist() if cfg.pde_mode=="spectrum" else [],
            "pde_original_y": pde.y.tolist() if cfg.pde_mode=="spectrum" else [],
        }
        result["integration"] = {
            "wavelength_nm":x.tolist(),"weights_nm":w.tolist(),
            "solar_radiance":sun_l.tolist(),"other_radiance":ambient_l.tolist(),
            "filter_transmission":t.tolist(),"pde":pde_at(x).tolist(),
            "detector_weight":detector_weight.tolist(),
        }
    return result

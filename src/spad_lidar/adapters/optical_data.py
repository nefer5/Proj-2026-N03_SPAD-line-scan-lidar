"""Versioned offline optical dataset. No implicit normalization or extrapolation."""
from typing import Literal
from pydantic import Field
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from ..spad.config import StrictConfig


class TxData(StrictConfig):
    reference_plane: Literal['after_tx_optics']
    h_edges_mrad: list[float]
    v_edges_mrad: list[float]
    energy_fraction: list[list[float]]


class RxData(StrictConfig):
    reference_plane: Literal['pupil_to_unbounded_image_before_filter_and_PDE_FF']
    psf_convention: Literal['fraction_of_unbounded_PSF_in_each_full_pixel_no_edge_renormalization']
    wavelength_nm: list[float]
    h_angle_mrad: list[float]
    v_angle_mrad: list[float]
    x_edges_um: list[float]
    y_edges_um: list[float]
    collection_efficiency: list
    psf_pixel_fraction: list


class OpticalDataset(StrictConfig):
    schema_version: Literal[1]
    coordinate_convention: Literal['optical_H_right_V_down__image_x_right_y_down']
    label: str = Field(min_length=1)
    synthetic: bool
    provenance: dict
    tx: TxData
    rx: RxData


def axis(values, name, minimum):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or len(a) < minimum or not np.all(np.isfinite(a)) or np.any(np.diff(a) <= 0):
        raise ValueError(f'{name}: axis must be finite and strictly increasing, with at least {minimum} samples')
    return a


def validate_dataset(document, algorithms):
    data = OpticalDataset.model_validate(document)
    tx, rx = data.tx, data.rx
    th = axis(tx.h_edges_mrad,'tx.h_edges_mrad',2); tv = axis(tx.v_edges_mrad,'tx.v_edges_mrad',2)
    wl = axis(rx.wavelength_nm,'rx.wavelength_nm',1)
    h = axis(rx.h_angle_mrad,'rx.h_angle_mrad',1); v = axis(rx.v_angle_mrad,'rx.v_angle_mrad',1)
    x = axis(rx.x_edges_um,'rx.x_edges_um',2); y = axis(rx.y_edges_um,'rx.y_edges_um',2)
    if np.any(wl <= 0):
        raise ValueError('Dataset wavelengths must be positive')
    if max(np.abs(th).max(),np.abs(tv).max(),np.abs(h).max(),np.abs(v).max()) > algorithms.max_spatial_angle_mrad:
        raise ValueError('Optical angles exceed configured paraxial model domain')
    shape = (len(wl),len(v),len(h))
    if (len(tv)-1)*(len(th)-1)>algorithms.max_optical_cells:
        raise ValueError('Tx angular dataset exceeds max_optical_cells')
    full_shape = (*shape,len(y)-1,len(x)-1)
    if np.prod(full_shape) > algorithms.max_optical_cells:
        raise ValueError('Optical dataset exceeds max_optical_cells')
    fraction = np.asarray(tx.energy_fraction,dtype=float)
    eff = np.asarray(rx.collection_efficiency,dtype=float)
    psf = np.asarray(rx.psf_pixel_fraction,dtype=float)
    if fraction.shape != (len(tv)-1,len(th)-1) or eff.shape != shape or psf.shape != full_shape:
        raise ValueError('Optical array shapes do not match their explicit axes')
    for name, values in [('Tx fractions',fraction),('Rx efficiencies',eff),('PSF fractions',psf)]:
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError(name+' must be finite and nonnegative')
    tol=algorithms.energy_conservation_rtol
    if fraction.sum() > 1+tol or np.any(eff > 1) or np.any(psf.sum(axis=(-2,-1)) > 1+tol):
        raise ValueError('Energy fractions exceed unity; data will not be clipped or renormalized')
    return data


class RxTable:
    def __init__(self, data):
        self.axes = tuple(np.asarray(a,dtype=float) for a in (data.wavelength_nm,data.v_angle_mrad,data.h_angle_mrad))
        self.eff = RegularGridInterpolator(self.axes,np.asarray(data.collection_efficiency,dtype=float),bounds_error=True)
        self.psf = RegularGridInterpolator(self.axes,np.asarray(data.psf_pixel_fraction,dtype=float),bounds_error=True)

    def evaluate(self, wavelength_nm, h_mrad, v_mrad):
        points=np.column_stack((np.full(np.size(h_mrad),wavelength_nm),np.ravel(v_mrad),np.ravel(h_mrad)))
        try:
            return self.eff(points),self.psf(points)
        except ValueError as exc:
            raise ValueError('Rx database does not cover the requested angle/wavelength; extrapolation is disabled') from exc

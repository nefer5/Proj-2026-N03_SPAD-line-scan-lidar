"""Tx cell fractions normalized within the explicitly configured angular domain."""
import numpy as np
from scipy.special import ndtr
from ..constants import FWHM_TO_SIGMA


def transmit(energy_j, efficiency):
    return energy_j * efficiency


def normalize_angular_weights(weights):
    """The pulse energy belongs to this domain; weights describe only its shape."""
    values = np.asarray(weights, dtype=float)
    total = values.sum()
    if not np.all(np.isfinite(values)) or np.any(values < 0) or not np.isfinite(total) or total <= 0:
        raise ValueError('Tx angular domain must have finite nonnegative weights with a positive sum; cannot normalize')
    return values / total


def gaussian_axis_fractions(edges, center, sigma):
    z = (edges-center)/sigma
    # Reflect positive-tail intervals to avoid subtracting two CDF values of 1.
    lower, upper = z[:-1], z[1:]
    mass = np.where(lower >= 0, ndtr(-lower)-ndtr(-upper), ndtr(upper)-ndtr(lower))
    return normalize_angular_weights(mass)


def angular_profile(optics, algorithms):
    if algorithms.spatial_angle_samples_h*algorithms.spatial_angle_samples_v > algorithms.max_optical_cells:
        raise ValueError('Tx angular grid exceeds max_optical_cells before allocation')
    h = np.linspace(optics.angle_h_min_mrad, optics.angle_h_max_mrad, algorithms.spatial_angle_samples_h+1)
    v = np.linspace(optics.angle_v_min_mrad, optics.angle_v_max_mrad, algorithms.spatial_angle_samples_v+1)
    if optics.tx_model == 'uniform':
        fractions = np.outer(np.diff(v)/(v[-1]-v[0]), np.diff(h)/(h[-1]-h[0]))
    else:
        fh = gaussian_axis_fractions(h, optics.tx_center_h_mrad, optics.tx_fwhm_h_mrad/FWHM_TO_SIGMA)
        fv = gaussian_axis_fractions(v, optics.tx_center_v_mrad, optics.tx_fwhm_v_mrad/FWHM_TO_SIGMA)
        fractions = np.outer(fv, fh)
    return h, v, normalize_angular_weights(fractions)

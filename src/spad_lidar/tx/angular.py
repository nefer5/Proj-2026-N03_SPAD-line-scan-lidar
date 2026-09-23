"""Tx far-field cell fractions; finite angular support is never renormalized."""
import numpy as np
from scipy.special import ndtr
from ..constants import FWHM_TO_SIGMA


def transmit(energy_j, efficiency):
    return energy_j * efficiency


def angular_profile(optics, algorithms):
    if algorithms.spatial_angle_samples_h*algorithms.spatial_angle_samples_v > algorithms.max_optical_cells:
        raise ValueError('Tx angular grid exceeds max_optical_cells before allocation')
    h = np.linspace(optics.angle_h_min_mrad, optics.angle_h_max_mrad, algorithms.spatial_angle_samples_h+1)
    v = np.linspace(optics.angle_v_min_mrad, optics.angle_v_max_mrad, algorithms.spatial_angle_samples_v+1)
    if optics.tx_model == 'uniform':
        fractions = np.outer(np.diff(v)/(v[-1]-v[0]), np.diff(h)/(h[-1]-h[0]))
    else:
        fh = np.diff(ndtr((h-optics.tx_center_h_mrad)/(optics.tx_fwhm_h_mrad/FWHM_TO_SIGMA)))
        fv = np.diff(ndtr((v-optics.tx_center_v_mrad)/(optics.tx_fwhm_v_mrad/FWHM_TO_SIGMA)))
        fractions = np.outer(fv, fh)
    return h, v, fractions

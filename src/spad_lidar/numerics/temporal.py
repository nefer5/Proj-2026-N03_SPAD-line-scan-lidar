from math import sqrt
from ..constants import FWHM_TO_SIGMA
import numpy as np
from scipy.special import ndtr


def pulse_interval_fractions(centers_ns,lower_ns,upper_ns,shape,fwhm_ps):
    """Fraction of emitted pulse energy inside a time interval, without detector jitter."""
    centers=np.asarray(centers_ns,dtype=float)
    width=fwhm_ps*1e-3
    if shape=='gaussian':
        sigma=width/FWHM_TO_SIGMA
        return ndtr((upper_ns-centers)/sigma)-ndtr((lower_ns-centers)/sigma)
    if shape=='rectangular':
        return np.clip((upper_ns-centers)/width+.5,0,1)-np.clip((lower_ns-centers)/width+.5,0,1)
    raise ValueError('Unsupported incident pulse distribution')


def sample_pulse_offsets(rng, shape, fwhm_ps, count):
    """Incident temporal distribution; output ns, no device or electronics jitter."""
    if shape == 'gaussian':
        return rng.normal(0, fwhm_ps/FWHM_TO_SIGMA, count)*1e-3
    if shape == 'rectangular':
        return rng.uniform(-fwhm_ps/2, fwhm_ps/2, count)*1e-3
    raise ValueError('Unsupported incident pulse distribution')

def timing_sigma_ns(cfg):
    laser_sigma = cfg.pulse_fwhm_ps / (
        FWHM_TO_SIGMA if cfg.pulse_shape == "gaussian" else sqrt(12)
    )
    return sqrt(laser_sigma**2 + (cfg.spad_jitter_fwhm_ps / FWHM_TO_SIGMA)**2
                + (cfg.other_jitter_fwhm_ps / FWHM_TO_SIGMA)**2) * 1e-3


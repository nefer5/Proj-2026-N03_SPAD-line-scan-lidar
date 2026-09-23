"""Single owner of photon conversion and intrinsic device time response."""
import numpy as np
from ...constants import C, H, FWHM_TO_SIGMA


def effective_pde(pde, fill_factor):
    return pde * fill_factor


def spectral_detection_weights(transmission, pde, wavelength_nm):
    # Preserve A's operation order while centralizing PDE weighting.
    return transmission * pde * wavelength_nm * 1e-9 / (H * C)


def apply_jitter(rng, times, fwhm_ps):
    return times + rng.normal(0, fwhm_ps / FWHM_TO_SIGMA * 1e-3, len(times))

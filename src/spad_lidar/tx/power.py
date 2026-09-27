"""Single-pulse equivalent average power at the VCSEL / pre-Tx plane."""
import math


def pulse_energy_nj(average_power_w, pulse_fwhm_ps):
    # Gaussian: FWHM is the explicitly chosen equivalent duration, not finite support.
    value=average_power_w*pulse_fwhm_ps*1e-3
    if not math.isfinite(value):raise ValueError('Pulse energy is not finite')
    return value

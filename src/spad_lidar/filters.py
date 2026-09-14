"""One spectral response for plotting, laser throughput and background integral."""
import numpy as np
from scipy.interpolate import PchipInterpolator


class FilterResponse:
    def __init__(self, cfg):
        self.has_samples = cfg.filter_curve is not None
        if self.has_samples:
            self.wavelength = np.array([p.wavelength_nm for p in cfg.filter_curve], dtype=float)
            self.transmission = np.array([p.transmission for p in cfg.filter_curve], dtype=float)
            self.method = cfg.filter_interpolation
        else:
            half = cfg.filter_bandwidth_nm / 2
            self.wavelength = np.array([cfg.wavelength_nm-half, cfg.wavelength_nm+half])
            self.transmission = np.full(2, cfg.filter_peak_transmission)
            self.method = "rectangular"
        self.polynomial = (PchipInterpolator(self.wavelength, self.transmission, extrapolate=False)
                           if self.method == "pchip" else None)

    def evaluate(self, wavelength_nm):
        x = np.asarray(wavelength_nm, dtype=float)
        inside = (x >= self.wavelength[0]) & (x <= self.wavelength[-1])
        if self.polynomial is not None:
            values = self.polynomial(x)
        else:
            values = np.interp(x, self.wavelength, self.transmission)
        # No extrapolation: out-of-band throughput is defined as zero.
        result = np.where(inside, values, 0.0)
        return float(result) if result.ndim == 0 else result

    def integral_nm(self):
        if self.polynomial is not None:
            # Exact integral of the piecewise cubic, independent of plot density.
            return float(self.polynomial.integrate(self.wavelength[0], self.wavelength[-1]))
        return float(np.trapezoid(self.transmission, self.wavelength))

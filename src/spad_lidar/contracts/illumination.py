from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SensorIllumination:
    """Spectrally integrated cells: [pixel, wavelength], BEFORE PDE/FF.

    Values are photons/pulse or photons/second, not densities per wavelength.
    A spectral quadrature provider must include its wavelength integration weights.
    Pixel plane includes inactive area; FF is exclusively a device response.
    """
    wavelength_nm: np.ndarray
    signal_photons_per_pulse: np.ndarray
    background_photons_per_second: np.ndarray
    pulse_shape: str
    pulse_fwhm_ps: float
    pulse_delay_ns: float
    provenance: dict

    def __post_init__(self):
        wl = np.asarray(self.wavelength_nm, dtype=float)
        signal = np.asarray(self.signal_photons_per_pulse, dtype=float)
        background = np.asarray(self.background_photons_per_second, dtype=float)
        if wl.ndim != 1 or not len(wl) or np.any(wl <= 0) or not np.all(np.isfinite(wl)):
            raise ValueError('Illumination wavelengths must be finite and positive')
        if signal.ndim != 2 or signal.shape[1] != len(wl) or background.shape != signal.shape:
            raise ValueError('Illumination requires aligned [pixel,wavelength] arrays')
        if not signal.shape[0] or any(not np.all(np.isfinite(a)) or np.any(a < 0) for a in (signal, background)):
            raise ValueError('Illumination must contain finite nonnegative photon measures')
        if self.pulse_shape not in ('gaussian', 'rectangular'):
            raise ValueError('Unsupported incident pulse shape')
        if not np.isfinite(self.pulse_fwhm_ps) or self.pulse_fwhm_ps <= 0 or not np.isfinite(self.pulse_delay_ns):
            raise ValueError('Invalid incident temporal distribution')
        object.__setattr__(self, 'wavelength_nm', wl)
        object.__setattr__(self, 'signal_photons_per_pulse', signal)
        object.__setattr__(self, 'background_photons_per_second', background)

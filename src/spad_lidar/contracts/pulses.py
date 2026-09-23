from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class IncidentPulseGroup:
    """A source pulse may have several flight-time components, BEFORE PDE/FF.

    photons_per_pixel is [component,physical_pixel]; each component is monochromatic
    and has its own absolute arrival center. Zero rows mean a blanked source.
    """
    photons_per_pixel: np.ndarray
    wavelength_nm: np.ndarray
    arrival_center_ns: np.ndarray
    pulse_shape: str
    pulse_fwhm_ps: float

    def __post_init__(self):
        photons=np.asarray(self.photons_per_pixel,dtype=float)
        wavelengths=np.asarray(self.wavelength_nm,dtype=float)
        centers=np.asarray(self.arrival_center_ns,dtype=float)
        if photons.ndim!=2 or not all(photons.shape) or wavelengths.shape!=(photons.shape[0],) or centers.shape!=wavelengths.shape:
            raise ValueError('Incident pulse components require aligned component/pixel, wavelength and time arrays')
        if not all(np.all(np.isfinite(x)) for x in (photons,wavelengths,centers)) or np.any(photons<0) or np.any(wavelengths<=0):
            raise ValueError('Invalid incident photon components')
        if self.pulse_shape not in ('gaussian','rectangular') or not np.isfinite(self.pulse_fwhm_ps) or self.pulse_fwhm_ps<=0:
            raise ValueError('Invalid incident temporal distribution')
        object.__setattr__(self,'photons_per_pixel',photons)
        object.__setattr__(self,'wavelength_nm',wavelengths)
        object.__setattr__(self,'arrival_center_ns',centers)

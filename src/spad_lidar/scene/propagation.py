"""Static extended Lambertian target, with explicitly separated reference planes."""
from math import pi
import numpy as np


def lambertian_return(tx_output_j, one_way_transmission, reflectivity, aperture_m2, range_m, overlap):
    ranges=np.asarray(range_m,dtype=float)
    if np.any(ranges<=0) or not np.all(np.isfinite(ranges)):
        raise ValueError('Lambertian propagation requires finite positive range')
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        geometry=aperture_m2/(pi*ranges**2)
    if not np.all(np.isfinite(geometry)) or np.any(geometry>1) or np.any(geometry<0):
        raise ValueError('Lambertian far-field collection exceeds the energy-conserving domain; change range/aperture or use a near-field model')
    if geometry.ndim==0:
        geometry=float(geometry)
    incident = tx_output_j * one_way_transmission
    reflected = incident * reflectivity
    pupil = reflected * geometry * one_way_transmission * overlap
    return incident, reflected, pupil, geometry

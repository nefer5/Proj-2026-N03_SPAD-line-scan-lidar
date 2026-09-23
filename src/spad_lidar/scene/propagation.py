"""Static extended Lambertian target, with explicitly separated reference planes."""
from math import pi


def lambertian_return(tx_output_j, one_way_transmission, reflectivity, aperture_m2, range_m, overlap):
    incident = tx_output_j * one_way_transmission
    reflected = incident * reflectivity
    geometry = aperture_m2 / (pi * range_m**2)
    pupil = reflected * geometry * one_way_transmission * overlap
    return incident, reflected, pupil, geometry

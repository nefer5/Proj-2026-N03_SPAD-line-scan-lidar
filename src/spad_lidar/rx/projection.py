"""Shared signal reference planes for static and moving optical composition."""
from dataclasses import dataclass
from ..scene import lambertian_return


@dataclass(frozen=True)
class SignalProjection:
    target_incident: object
    target_reflected: object
    pupil: object
    geometry: object
    after_rx: object
    after_filter: object
    pixel_energy: object


def project_return(emitted_per_angle,atmosphere,reflectivity,area,ranges,overlap,efficiency,filter_transmission,psf):
    incident,reflected,pupil,geometry=lambertian_return(emitted_per_angle,atmosphere,reflectivity,area,ranges,overlap)
    after_rx=pupil*efficiency
    after_filter=after_rx*filter_transmission
    return SignalProjection(incident,reflected,pupil,geometry,after_rx,after_filter,after_filter@psf)

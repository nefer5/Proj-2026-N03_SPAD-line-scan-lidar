"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np
from math import pi, sqrt
from ..constants import C, H, FWHM_TO_SIGMA
from dataclasses import dataclass
from ..models import SimulationConfig
from ..filters import FilterResponse
from ..spectra import spectral_components
from ..spad.device.response import effective_pde
from ..tx import transmit
from ..scene import lambertian_return


@dataclass(frozen=True)
class Budget:
    signal_detected_per_pulse: float
    background_detected_per_gate: float
    dark_detected_per_gate: float
    other_detected_per_gate: float
    filter_enbw_nm: float
    filter_transmission_at_laser: float
    photon_energy_j: float
    aperture_area_m2: float
    received_signal_j: float
    background_power_w: float
    effective_pdp: float
    channel_solid_angle_sr: float
    emitted_energy_j: float
    geometric_collection: float
    solar_detected_per_gate: float
    other_light_detected_per_gate: float
    solar_background_power_w: float
    other_light_background_power_w: float
    pde_at_laser: float
    tx_output_energy_j: float
    target_incident_energy_j: float
    target_reflected_energy_j: float
    rx_incident_energy_j: float
    signal_rx_incident_photons_per_pulse: float
    signal_sensor_incident_photons_per_pulse: float
    solar_rx_incident_photons_per_gate: float
    other_rx_incident_photons_per_gate: float
    solar_sensor_incident_photons_per_gate: float
    other_sensor_incident_photons_per_gate: float
    solar_rx_incident_power_w: float
    other_rx_incident_power_w: float


def aperture_area(cfg: SimulationConfig) -> float:
    """Projected clear entrance pupil area; ellipse sizes are FULL axes."""
    if cfg.rx_aperture_shape == "circle":
        return pi * (cfg.rx_aperture_mm * 1e-3 / 2) ** 2
    area = cfg.rx_aperture_width_mm * cfg.rx_aperture_height_mm * 1e-6
    return area * pi / 4 if cfg.rx_aperture_shape == "ellipse" else area


def _filter_properties(cfg):
    response = FilterResponse(cfg)
    return response.integral_nm(), response.evaluate(cfg.wavelength_nm)


def photon_budget(cfg: SimulationConfig, range_m=None, spectral=None) -> Budget:
    r = cfg.range_m if range_m is None else range_m
    photon_energy = H * C / (cfg.wavelength_nm * 1e-9)
    area = aperture_area(cfg)
    enbw, transmission = _filter_properties(cfg)
    # Input reference plane is BEFORE Tx optics, for this angular channel.
    energy = cfg.pulse_energy_nj * 1e-9
    tx_output=transmit(energy,cfg.tx_efficiency)
    target_incident,target_reflected,rx_incident,geometry=lambertian_return(tx_output,cfg.atmospheric_one_way_transmission,cfg.target_reflectivity,area,r,cfg.overlap_factor)
    received=rx_incident*cfg.rx_efficiency*transmission
    spectral = spectral if spectral is not None else spectral_components(cfg)
    effective_pdp = effective_pde(spectral["pde_at_laser"], cfg.fill_factor)
    omega = cfg.channel_ifov_h_mrad * cfg.channel_ifov_v_mrad * 1e-6
    geometry_bg = area*omega*cfg.rx_efficiency
    solar_power = spectral["solar_filtered_radiance_w_m2_sr"]*geometry_bg
    other_power = spectral["other_filtered_radiance_w_m2_sr"]*geometry_bg
    background_power = solar_power+other_power
    gate_s = cfg.gate_width_ns * 1e-9
    solar_counts = spectral["solar_detectable_photons_s_m2_sr"]*geometry_bg*cfg.fill_factor*gate_s
    other_counts = spectral["other_detectable_photons_s_m2_sr"]*geometry_bg*cfg.fill_factor*gate_s
    return Budget(
        received / photon_energy * effective_pdp,
        solar_counts+other_counts,
        cfg.dcr_cps_per_spad * cfg.spads_per_channel * gate_s,
        cfg.other_noise_cps_per_spad * cfg.spads_per_channel * gate_s,
        enbw, transmission, photon_energy, area, received, background_power,
        effective_pdp, omega, energy, geometry, solar_counts, other_counts,
        solar_power, other_power, spectral["pde_at_laser"],
        tx_output,target_incident,target_reflected,rx_incident,
        rx_incident/photon_energy,received/photon_energy,
        spectral['solar_incident_photons_s_m2_sr']*area*omega*gate_s,
        spectral['other_incident_photons_s_m2_sr']*area*omega*gate_s,
        spectral['solar_filtered_photons_s_m2_sr']*geometry_bg*gate_s,
        spectral['other_filtered_photons_s_m2_sr']*geometry_bg*gate_s,
        spectral['solar_incident_radiance_w_m2_sr']*area*omega,
        spectral['other_incident_radiance_w_m2_sr']*area*omega,
    )


"""Bind shared photon-chain definitions to actual Python intermediate values."""
from hashlib import sha256
import json
from .configuration import read_yaml


def build_photon_flow(cfg,budget,spectral,gate_fraction):
    b=budget
    values={
        "aperture_m2":b.aperture_area_m2,"omega_sr":b.channel_solid_angle_sr,
        "aperture_shape":cfg.rx_aperture_shape,
        "aperture_dimensions_m":("d="+str(cfg.rx_aperture_mm*1e-3) if cfg.rx_aperture_shape=='circle' else "W="+str(cfg.rx_aperture_width_mm*1e-3)+", H="+str(cfg.rx_aperture_height_mm*1e-3)),
        "ifov_h_mrad":cfg.channel_ifov_h_mrad,"ifov_v_mrad":cfg.channel_ifov_v_mrad,
        "tx_efficiency":cfg.tx_efficiency,
        "gate_s":cfg.gate_width_ns*1e-9,"lambda_nm":cfg.wavelength_nm,
        "photon_j":b.photon_energy_j,"band_min_nm":spectral["budget_band_nm"][0],
        "band_max_nm":spectral["budget_band_nm"][1],"shots":cfg.laser_shots,
        "rx_efficiency":cfg.rx_efficiency,"fill_factor":cfg.fill_factor,
        "echo_input_j":b.emitted_energy_j,"echo_tx_j":b.tx_output_energy_j,
        "echo_target_j":b.target_incident_energy_j,"echo_reflected_j":b.target_reflected_energy_j,
        "rho_laser":cfg.target_reflectivity,"atmosphere":cfg.atmospheric_one_way_transmission,
        "range_m":cfg.range_m,"geometry":b.geometric_collection,"overlap":cfg.overlap_factor,
        "echo_rx_j":b.rx_incident_energy_j,"echo_rx_photons":b.signal_rx_incident_photons_per_pulse,
        "filter_at_laser":b.filter_transmission_at_laser,
        "echo_sensor_j":b.received_signal_j,"echo_sensor_photons":b.signal_sensor_incident_photons_per_pulse,
        "pde_at_laser":b.pde_at_laser,"echo_candidates_pulse":b.signal_detected_per_pulse,
        "echo_gate_fraction":gate_fraction,"echo_candidates_gate":b.signal_detected_per_pulse*gate_fraction,
        "echo_candidates_acquisition":b.signal_detected_per_pulse*gate_fraction*cfg.laser_shots,
        "solar_enabled":cfg.solar_enabled,"solar_requested_lux":cfg.solar_illuminance_lux,
        "solar_actual_lux":spectral["solar_lux"],"solar_reference_lux":spectral["solar_reference_lux"],
        "solar_scale":spectral["solar_scale"],"solar_irradiance_w_m2":spectral["solar_irradiance_w_m2"],
        "solar_source":spectral["standard"],
        "solar_reference_irradiance":spectral["solar_reference_irradiance_w_m2"],
        "rho_solar":cfg.solar_reflectivity,
        "solar_irradiance_at_laser":spectral["solar_irradiance_at_laser_w_m2_nm"],
        "solar_radiance_at_laser":spectral["solar_radiance_at_laser_w_m2_sr_nm"],
        "other_enabled":cfg.other_light_enabled,"other_scale":cfg.other_light_scale,
        "other_raw_radiance_at_laser":spectral["other_raw_radiance_at_laser_w_m2_sr_nm"],
        "other_radiance_at_laser":spectral["other_radiance_at_laser_w_m2_sr_nm"],
        "solar_rx_power_w":b.solar_rx_incident_power_w,
        "other_rx_power_w":b.other_rx_incident_power_w,
        "solar_rx_photons_gate":b.solar_rx_incident_photons_per_gate,
        "other_rx_photons_gate":b.other_rx_incident_photons_per_gate,
        "solar_sensor_power_w":b.solar_background_power_w,
        "other_sensor_power_w":b.other_light_background_power_w,
        "solar_sensor_photons_gate":b.solar_sensor_incident_photons_per_gate,
        "other_sensor_photons_gate":b.other_sensor_incident_photons_per_gate,
        "solar_candidates_gate":b.solar_detected_per_gate,"other_candidates_gate":b.other_light_detected_per_gate,
        "solar_candidates_acquisition":b.solar_detected_per_gate*cfg.laser_shots,
        "other_candidates_acquisition":b.other_light_detected_per_gate*cfg.laser_shots,
        "dark_gate":b.dark_detected_per_gate,"electronic_gate":b.other_detected_per_gate,
        "background_gate":b.background_detected_per_gate,
        "noise_gate":b.background_detected_per_gate+b.dark_detected_per_gate+b.other_detected_per_gate,
        "readout_mode":cfg.readout_mode,
    }
    definition=read_yaml("photon-flow.yaml")
    formulas=read_yaml("formulas.yaml")
    notes=read_yaml("formula-notes.yaml")
    def bind(step):
        fid=step["formula_id"]
        return {**step,"latex":formulas[fid],"symbols":notes[fid],
                "values":[{**v,"value":values[v["key"]]} for v in step["values"]]}
    return {
        "title":definition["title"],"intro":definition["intro"],"conventions":definition["conventions"],
        "input_sha256":sha256(json.dumps(cfg.model_dump(),sort_keys=True).encode()).hexdigest(),
        "common":[bind(s) for s in definition["common"]],
        "chains":[{**c,"steps":[bind(s) for s in c["steps"]]} for c in definition["chains"]],
        "readout":[bind(s) for s in definition["readout"]],
        "values":values,
        "numerics":{"quadrature_band_nm":spectral["budget_band_nm"],
                    "solar_source":spectral["standard"],"input_modes":spectral["input_modes"]},
    }

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .configuration import default_values, Algorithms, read_yaml
from .constants import C
from .curves import SpectralInputs
from .legacy_config import migrate


class FilterPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wavelength_nm: float = Field(gt=0)
    transmission: float = Field(ge=0.0, le=1.0)


class RadiancePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wavelength_nm: float = Field(gt=0)
    radiance: float = Field(ge=0)


class PDEPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wavelength_nm: float = Field(gt=0)
    pde: float = Field(ge=0, le=1)


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    pulse_shape: Literal["gaussian", "rectangular"]
    laser_prf_hz: float = Field(gt=0)
    rx_aperture_shape: Literal["circle", "ellipse", "rectangle"]
    rx_aperture_width_mm: float = Field(gt=0)
    rx_aperture_height_mm: float = Field(gt=0)

    @model_validator(mode="before")
    @classmethod
    def resolve_defaults(cls, values):
        if not isinstance(values, dict):
            return values
        defaults = default_values()
        if set(defaults) != set(cls.model_fields):
            raise ValueError("defaults.yaml keys do not match SimulationConfig fields")
        return migrate(values, defaults)

    # Scene and laser. Pulse energy is for the angular channel being evaluated.
    range_m: float = Field(gt=0.0)
    target_reflectivity: float = Field(ge=0.0, le=1.0)
    wavelength_nm: float = Field(gt=0.0)
    pulse_energy_nj: float = Field(ge=0.0)
    tx_efficiency: float = Field(ge=0.0, le=1.0)
    overlap_factor: float = Field(ge=0.0, le=1.0)
    atmospheric_one_way_transmission: float = Field(ge=0.0, le=1.0)

    spectral_inputs: SpectralInputs

    @property
    def pde(self):
        # Deprecated scalar compatibility accessor; new calculations use Curve.
        return self.spectral_inputs.pde.basic.amplitude

    @property
    def background_spectral_radiance(self):
        return self.spectral_inputs.other.basic.amplitude

    # Receiver optics abstraction.
    rx_aperture_mm: float = Field(gt=0.0)
    rx_efficiency: float = Field(ge=0.0, le=1.0)
    channel_ifov_h_mrad: float = Field(gt=0.0)
    channel_ifov_v_mrad: float = Field(gt=0.0)

    # Scene background is spectral radiance at the receiver direction.
    solar_enabled: bool
    solar_illuminance_lux: float = Field(ge=0)
    solar_reflectivity: float = Field(ge=0, le=1)
    other_light_enabled: bool
    other_light_scale: float = Field(ge=0)

    # SPAD and readout.
    spads_per_channel: int = Field(ge=1)
    fill_factor: float = Field(gt=0.0, le=1.0)
    dcr_cps_per_spad: float = Field(ge=0.0)
    other_noise_cps_per_spad: float = Field(ge=0.0)
    spad_dead_time_ns: float = Field(ge=0.0)
    readout_mode: str
    detector_operation: Literal["gated", "free_running"]
    tdc_dead_time_ns: float = Field(ge=0)
    tdc_count: int = Field(ge=1)
    tdc_max_hits_per_cycle: int = Field(ge=1)
    or_pulse_width_ns: float = Field(ge=0)
    coincidence_window_ns: float = Field(gt=0)
    coincidence_threshold: int = Field(ge=1)
    spad_jitter_fwhm_ps: float = Field(ge=0.0)

    # Timing and acquisition.
    pulse_fwhm_ps: float = Field(gt=0.0)
    other_jitter_fwhm_ps: float = Field(ge=0.0)
    tdc_bin_ps: float = Field(gt=0.0)
    gate_start_ns: float = Field(ge=0.0)
    gate_width_ns: float = Field(gt=0.0)
    calibration_delay_ns: float
    laser_shots: int = Field(ge=1)
    monte_carlo_trials: int = Field(ge=0)
    rng_seed: int = Field(ge=0)

    # Simple line-channel crosstalk abstraction.
    line_channels: int = Field(ge=2)
    nearest_neighbor_crosstalk: float = Field(ge=0.0, lt=1.0)
    crosstalk_decay_channels: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_histogram_size(self):
        bins = self.gate_width_ns * 1000.0 / self.tdc_bin_ps
        algorithms = Algorithms.load()
        if self.readout_mode not in read_yaml('readout-modes.yaml'):
            raise ValueError('Unknown readout_mode')
        if self.tdc_count > algorithms.max_spads_per_channel:
            raise ValueError('tdc_count exceeds resource limit')
        if self.readout_mode.startswith('coincidence') and self.coincidence_threshold > self.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds SPAD count')
        for field in ('spads_per_channel', 'laser_shots', 'monte_carlo_trials', 'line_channels'):
            if getattr(self, field) > getattr(algorithms, 'max_' + field):
                raise ValueError(f'{field} exceeds configured resource limit')
        if bins > algorithms.max_histogram_bins:
            raise ValueError("Histogram bin count exceeds config/algorithms.yaml limit")
        tof_ns = 2.0 * self.range_m / C * 1e9 + self.calibration_delay_ns
        if not (self.gate_start_ns <= tof_ns <= self.gate_start_ns + self.gate_width_ns):
            raise ValueError("target time of flight falls outside the acquisition gate")
        if self.gate_start_ns + self.gate_width_ns > 1e9 / self.laser_prf_hz:
            raise ValueError("Acquisition gate exceeds laser repetition period; reduce PRF or gate")
        if self.pulse_fwhm_ps * 1e-12 >= 1 / self.laser_prf_hz:
            raise ValueError("Pulse width must be shorter than repetition period")
        return self

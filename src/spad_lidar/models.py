from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class FilterPoint(BaseModel):
    wavelength_nm: float
    transmission: float = Field(ge=0.0, le=1.0)


class SimulationConfig(BaseModel):
    # Scene and laser. Pulse energy is for the angular channel being evaluated.
    range_m: float = Field(50.0, gt=0.0)
    target_reflectivity: float = Field(0.10, ge=0.0, le=1.0)
    wavelength_nm: float = Field(940.0, gt=0.0)
    pulse_energy_nj: float = Field(5.0, ge=0.0)
    tx_efficiency: float = Field(0.80, ge=0.0, le=1.0)
    overlap_factor: float = Field(1.0, ge=0.0, le=1.0)
    atmospheric_one_way_transmission: float = Field(0.95, ge=0.0, le=1.0)

    # Receiver optics abstraction.
    rx_aperture_mm: float = Field(20.0, gt=0.0)
    rx_efficiency: float = Field(0.50, ge=0.0, le=1.0)
    channel_ifov_h_mrad: float = Field(0.20, gt=0.0)
    channel_ifov_v_mrad: float = Field(0.20, gt=0.0)
    filter_bandwidth_nm: float = Field(10.0, gt=0.0)
    filter_peak_transmission: float = Field(0.80, ge=0.0, le=1.0)
    filter_curve: list[FilterPoint] | None = None

    # Scene background is spectral radiance at the receiver direction.
    background_spectral_radiance: float = Field(0.020, ge=0.0)

    # SPAD and readout.
    spads_per_channel: int = Field(16, ge=1, le=4096)
    pde: float = Field(0.15, ge=0.0, le=1.0)
    fill_factor: float = Field(0.20, gt=0.0, le=1.0)
    dcr_cps_per_spad: float = Field(1000.0, ge=0.0)
    other_noise_cps_per_spad: float = Field(0.0, ge=0.0)
    spad_dead_time_ns: float = Field(20.0, ge=0.0)
    spad_jitter_fwhm_ps: float = Field(150.0, ge=0.0)

    # Timing and acquisition.
    pulse_fwhm_ps: float = Field(700.0, gt=0.0)
    other_jitter_fwhm_ps: float = Field(80.0, ge=0.0)
    tdc_bin_ps: float = Field(100.0, gt=0.0)
    gate_start_ns: float = Field(0.0, ge=0.0)
    gate_width_ns: float = Field(700.0, gt=0.0)
    calibration_delay_ns: float = 0.0
    laser_shots: int = Field(20_000, ge=1, le=100_000_000)
    monte_carlo_trials: int = Field(80, ge=0, le=500)
    rng_seed: int = 7

    # Simple line-channel crosstalk abstraction.
    line_channels: int = Field(16, ge=2, le=128)
    nearest_neighbor_crosstalk: float = Field(0.005, ge=0.0, lt=1.0)
    crosstalk_decay_channels: float = Field(0.8, gt=0.0)

    @model_validator(mode="after")
    def validate_histogram_size(self):
        bins = self.gate_width_ns * 1000.0 / self.tdc_bin_ps
        if bins > 50_000:
            raise ValueError("gate_width_ns / tdc_bin_ps produces more than 50,000 bins")
        tof_ns = 2.0 * self.range_m / 299_792_458.0 * 1e9 + self.calibration_delay_ns
        if not (self.gate_start_ns <= tof_ns <= self.gate_start_ns + self.gate_width_ns):
            raise ValueError("target time of flight falls outside the acquisition gate")
        return self


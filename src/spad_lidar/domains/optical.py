"""Shared optical field definitions and validated flat compatibility view."""
from typing import Literal
from pydantic import Field, model_validator
from ..spad.config import StrictConfig


class OpticalConfig(StrictConfig):
    tx_model: Literal['gaussian','super_gaussian','uniform','dataset']
    rx_model: Literal['gaussian_psf','super_gaussian_psf','uniform_pixel','dataset']
    dataset: dict | None
    channels_h: int = Field(ge=1,strict=True)
    channels_v: int = Field(ge=1,strict=True)
    pixel_pitch_um: float = Field(gt=0)
    focal_length_h_mm: float = Field(gt=0)
    focal_length_v_mm: float = Field(gt=0)
    mapping_mode: Literal['inverted','legacy_upright']
    tx_fwhm_h_mrad: float = Field(gt=0)
    tx_fwhm_v_mrad: float = Field(gt=0)
    tx_center_h_mrad: float
    tx_center_v_mrad: float
    tx_order_h: float = Field(ge=1)
    tx_order_v: float = Field(ge=1)
    psf_sigma_h_um: float = Field(gt=0)
    psf_sigma_v_um: float = Field(gt=0)
    psf_order_h: float = Field(ge=1)
    psf_order_v: float = Field(ge=1)
    rx_offset_x_um: float
    rx_offset_y_um: float
    angle_h_min_mrad: float
    angle_h_max_mrad: float
    angle_v_min_mrad: float
    angle_v_max_mrad: float
    rx_angle_h_min_mrad: float
    rx_angle_h_max_mrad: float
    rx_angle_v_min_mrad: float
    rx_angle_v_max_mrad: float
    pulse_average_power_w: float = Field(ge=0)
    range_m: float = Field(gt=0)
    target_reflectivity: float = Field(ge=0,le=1)
    wavelength_nm: float = Field(gt=0)
    pulse_shape: Literal['gaussian','rectangular']
    pulse_fwhm_ps: float = Field(gt=0)
    tx_efficiency: float = Field(ge=0,le=1)
    atmospheric_one_way_transmission: float = Field(ge=0,le=1)
    overlap_factor: float = Field(ge=0,le=1)
    rx_efficiency: float = Field(ge=0,le=1)
    rx_aperture_shape: Literal['circle','ellipse','rectangle']
    rx_aperture_mm: float = Field(gt=0)
    rx_aperture_width_mm: float = Field(gt=0)
    rx_aperture_height_mm: float = Field(gt=0)
    solar_enabled: bool
    solar_illuminance_lux: float = Field(ge=0)
    solar_reflectivity: float = Field(ge=0,le=1)
    other_light_enabled: bool
    other_light_scale: float = Field(ge=0)
    calibration_delay_ns: float

    @property
    def total_pulse_energy_nj(self):
        from ..tx.power import pulse_energy_nj
        return pulse_energy_nj(self.pulse_average_power_w,self.pulse_fwhm_ps)

    @model_validator(mode='after')
    def valid(self):
        if self.angle_h_max_mrad<=self.angle_h_min_mrad or self.angle_v_max_mrad<=self.angle_v_min_mrad:
            raise ValueError('Angular domain edges must be increasing')
        if self.rx_angle_h_max_mrad<=self.rx_angle_h_min_mrad or self.rx_angle_v_max_mrad<=self.rx_angle_v_min_mrad:
            raise ValueError('Receiver angular coverage edges must increase')
        if (self.tx_model=='dataset' or self.rx_model=='dataset') and self.dataset is None:
            raise ValueError('Selected optical model requires an explicit dataset')
        return self

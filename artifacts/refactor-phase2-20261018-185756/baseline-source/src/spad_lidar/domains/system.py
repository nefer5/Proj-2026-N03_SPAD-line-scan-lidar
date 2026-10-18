"""Canonical optical/device domain types; no experiment or YAML dependency."""
from copy import deepcopy
from pydantic import Field, create_model
from ..spad.config import StrictConfig, DeviceConfig
from .acquisition import TimingConfig
from .optical import OpticalConfig


OPTICAL_GROUPS = {
    'tx': ('tx_model','wavelength_nm','pulse_average_power_w','pulse_shape','pulse_fwhm_ps',
           'tx_efficiency','tx_fwhm_h_mrad','tx_fwhm_v_mrad','tx_center_h_mrad','tx_center_v_mrad','tx_order_h','tx_order_v',
           'angle_h_min_mrad','angle_h_max_mrad','angle_v_min_mrad','angle_v_max_mrad'),
    'scene': ('range_m','target_reflectivity','atmospheric_one_way_transmission','overlap_factor'),
    'rx': ('rx_model','focal_length_h_mm','focal_length_v_mm','mapping_mode','psf_sigma_h_um','psf_sigma_v_um','psf_order_h','psf_order_v',
           'rx_offset_x_um','rx_offset_y_um','rx_efficiency','rx_aperture_shape','rx_aperture_mm',
           'rx_aperture_width_mm','rx_aperture_height_mm','rx_angle_h_min_mrad','rx_angle_h_max_mrad',
           'rx_angle_v_min_mrad','rx_angle_v_max_mrad','dataset'),
    'spad': ('channels_h','channels_v','pixel_pitch_um'),
    'background': ('solar_enabled','solar_illuminance_lux','solar_reflectivity','other_light_enabled','other_light_scale'),
    'acquisition': ('calibration_delay_ns',),
}


def optical_fields(group):
    return {key: (OpticalConfig.model_fields[key].annotation, deepcopy(OpticalConfig.model_fields[key]))
            for key in OPTICAL_GROUPS[group]}


_TxFields = create_model('TxFields', __base__=StrictConfig, **optical_fields('tx'))


class TxConfig(_TxFields):
    @property
    def total_pulse_energy_nj(self):
        from ..tx.power import pulse_energy_nj
        return pulse_energy_nj(self.pulse_average_power_w,self.pulse_fwhm_ps)
SceneConfig = create_model('SceneConfig', __base__=StrictConfig, **optical_fields('scene'))
RxConfig = create_model('RxConfig', __base__=StrictConfig, **optical_fields('rx'))
SpadArrayConfig = create_model('SpadArrayConfig', __base__=DeviceConfig, **optical_fields('spad'))
BackgroundConfig = create_model('BackgroundConfig', __base__=StrictConfig, **optical_fields('background'))
AcquisitionConfig = create_model('AcquisitionConfig', __base__=TimingConfig,
    **optical_fields('acquisition'), monte_carlo_trials=(int, Field(ge=0, strict=True)),
    rng_seed=(int, Field(ge=0, strict=True)))


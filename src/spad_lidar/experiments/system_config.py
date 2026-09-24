"""Canonical B domain configuration; flat views exist only for shared legacy adapters."""
from copy import deepcopy
from functools import cached_property
from pydantic import Field, create_model, model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import SpectralInputs
from .configuration import TimingConfig
from .spatial import OpticalConfig

OPTICAL_GROUPS = {
    'tx': ('tx_model','wavelength_nm','total_pulse_energy_nj','pulse_shape','pulse_fwhm_ps',
           'tx_efficiency','tx_fwhm_h_mrad','tx_fwhm_v_mrad','tx_center_h_mrad','tx_center_v_mrad',
           'angle_h_min_mrad','angle_h_max_mrad','angle_v_min_mrad','angle_v_max_mrad'),
    'scene': ('range_m','target_reflectivity','atmospheric_one_way_transmission','overlap_factor'),
    'rx': ('rx_model','focal_length_h_mm','focal_length_v_mm','mapping_mode','psf_sigma_um',
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


TxConfig = create_model('TxConfig', __base__=StrictConfig, **optical_fields('tx'))
SceneConfig = create_model('SceneConfig', __base__=StrictConfig, **optical_fields('scene'))
RxConfig = create_model('RxConfig', __base__=StrictConfig, **optical_fields('rx'))
SpadArrayConfig = create_model('SpadArrayConfig', __base__=DeviceConfig, **optical_fields('spad'))
BackgroundConfig = create_model('BackgroundConfig', __base__=StrictConfig, **optical_fields('background'))
AcquisitionConfig = create_model('AcquisitionConfig', __base__=TimingConfig,
    **optical_fields('acquisition'), monte_carlo_trials=(int, Field(ge=0, strict=True)),
    rng_seed=(int, Field(ge=0, strict=True)))

LEGACY_PATHS = {f'optics.{key}': f'{group}.{key}' for group, keys in OPTICAL_GROUPS.items() for key in keys}
LEGACY_PATHS.update({f'device.{key}': f'spad.{key}' for key in DeviceConfig.model_fields})
LEGACY_PATHS.update({f'timing.{key}': f'acquisition.{key}' for key in TimingConfig.model_fields})
LEGACY_PATHS.update({'timing.monte_carlo_trials':'acquisition.monte_carlo_trials', 'rng_seed':'acquisition.rng_seed'})


class BSystemConfig(StrictConfig):
    tx: TxConfig
    scene: SceneConfig
    rx: RxConfig
    spad: SpadArrayConfig
    readout: ReadoutConfig
    background: BackgroundConfig
    acquisition: AcquisitionConfig
    spectral_inputs: SpectralInputs

    @cached_property
    def optics(self):
        values = {key: getattr(getattr(self,group),key) for group,keys in OPTICAL_GROUPS.items() for key in keys}
        return OpticalConfig.model_validate(values)

    @cached_property
    def device(self):
        return DeviceConfig.model_validate({key:getattr(self.spad,key) for key in DeviceConfig.model_fields})

    @cached_property
    def timing(self):
        return TimingConfig.model_validate({key:getattr(self.acquisition,key) for key in TimingConfig.model_fields})

    @property
    def rng_seed(self):
        return self.acquisition.rng_seed

    @model_validator(mode='after')
    def valid(self):
        self.optics  # Validate coupled optical domains and model/data requirements.
        if self.readout.readout_mode == 'analytic_reference':
            raise ValueError('B acquisition requires a digital readout mode')
        if self.readout.readout_mode.startswith('coincidence') and self.readout.coincidence_threshold > self.device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds H_binning × V_binning')
        if self.tx.pulse_fwhm_ps*1e-3 >= self.acquisition.period_ns:
            raise ValueError('Pulse width must be shorter than period')
        return self


def domain_defaults(base, additions):
    """Only references to the unique YAML defaults; no physical fallback values."""
    from ..curves import merge_config
    values = {group:{key:base[key] for key in keys if key in base} for group,keys in OPTICAL_GROUPS.items()}
    values['tx']['total_pulse_energy_nj'] = base['pulse_energy_nj']
    values['spad'].update({key:base[key] for key in DeviceConfig.model_fields})
    values['readout'] = {key:base[key] for key in ReadoutConfig.model_fields}
    values['acquisition'].update({key:base[key] for key in TimingConfig.model_fields if key!='period_ns'})
    values['acquisition'].update(period_ns=1e9/base['laser_prf_hz'],rng_seed=base['rng_seed'],monte_carlo_trials=base['monte_carlo_trials'])
    values['spectral_inputs'] = base['spectral_inputs']
    return merge_config(values,additions)


def form_values(cfg):
    """Bindings for existing shared widgets, never an alternative config store."""
    values={'device':cfg.device.model_dump(),'readout':cfg.readout.model_dump(),
            'timing':cfg.timing.model_dump(),'optics':cfg.optics.model_dump(),
            'spectral_inputs':cfg.spectral_inputs.model_dump(),'rng_seed':cfg.rng_seed}
    if isinstance(cfg,BSystemConfig) and hasattr(cfg.acquisition,'monte_carlo_trials'):
        values['timing']['monte_carlo_trials']=cfg.acquisition.monte_carlo_trials
    for name in ('scan','scene_motion'):
        if hasattr(cfg,name):values[name]=getattr(cfg,name).model_dump()
    return values

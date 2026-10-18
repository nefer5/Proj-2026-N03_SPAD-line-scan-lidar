"""Shared optical system contract and legacy views, without experiment dependencies."""
from functools import cached_property
from pydantic import model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import SpectralInputs
from .acquisition import TimingConfig
from .optical import OpticalConfig
from .system import (OPTICAL_GROUPS, TxConfig, SceneConfig, RxConfig, SpadArrayConfig, BackgroundConfig, AcquisitionConfig)


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
        self.validate_spatial_domains()
        if self.tx.pulse_fwhm_ps*1e-3 >= self.acquisition.period_ns:
            raise ValueError('Pulse width must be shorter than period')
        return self

    def validate_spatial_domains(self):
        self.optics  # Validate coupled optical domains and model/data requirements.
        if self.readout.readout_mode == 'analytic_reference':
            raise ValueError('B acquisition requires a digital readout mode')
        if self.readout.readout_mode.startswith('coincidence') and self.readout.coincidence_threshold > self.device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds H_binning × V_binning')
        return self

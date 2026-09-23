from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)


class DeviceConfig(StrictConfig):
    H_binning: int = Field(ge=1, strict=True)
    V_binning: int = Field(ge=1, strict=True)
    fill_factor: float = Field(gt=0, le=1)
    dcr_cps_per_spad: float = Field(ge=0)
    other_noise_cps_per_spad: float = Field(ge=0)
    spad_dead_time_ns: float = Field(ge=0)
    spad_jitter_fwhm_ps: float = Field(ge=0)
    detector_operation: Literal['gated', 'free_running']

    @property
    def spads_per_channel(self):
        return self.H_binning * self.V_binning


class ReadoutConfig(StrictConfig):
    readout_mode: Literal['independent_first', 'independent_multi', 'shared_first', 'shared_multi',
                         'shared_multitdc', 'coincidence_fixed', 'coincidence_sliding', 'analytic_reference']
    tdc_dead_time_ns: float = Field(ge=0)
    tdc_count: int = Field(ge=1, strict=True)
    tdc_max_hits_per_cycle: int = Field(ge=1, strict=True)
    or_pulse_width_ns: float = Field(ge=0)
    coincidence_window_ns: float = Field(gt=0)
    coincidence_threshold: int = Field(ge=1, strict=True)
    other_jitter_fwhm_ps: float = Field(ge=0)
    tdc_bin_ps: float = Field(gt=0)

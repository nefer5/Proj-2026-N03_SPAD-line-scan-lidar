from typing import Literal
from pydantic import Field, model_validator
from ..spad.config import StrictConfig
from ..constants import C


class ScanTiming(StrictConfig):
    period_ns: float = Field(gt=0)
    gate_start_ns: float = Field(ge=0)
    gate_width_ns: float = Field(gt=0)

    @model_validator(mode='after')
    def valid(self):
        if self.gate_start_ns+self.gate_width_ns>self.period_ns:
            raise ValueError('Acquisition gate exceeds trigger period')
        return self


class ScanSettings(StrictConfig):
    trajectory: Literal['static','sawtooth','triangle','sinusoidal']
    frame_rate_hz: float = Field(gt=0)
    frame_count: int = Field(ge=1,strict=True)
    active_fraction: float = Field(gt=0,lt=1)
    mechanical_start_mrad: float
    mechanical_end_mrad: float
    optical_multiplier: float
    optical_offset_mrad: float
    phase_offset_ns: float
    laser_time_offset_ns: float
    laser_jitter_std_ns: float = Field(ge=0)
    encoder_latency_ns: float
    encoder_angle_offset_mrad: float
    rx_scan_scale: float
    rx_angle_offset_mrad: float
    emission_policy: Literal['active_only','continuous']
    reconstruct_flyback: bool
    angle_bin_min_mrad: float
    angle_bin_max_mrad: float
    angle_bin_width_mrad: float = Field(gt=0)
    channel_direction_mode: Literal['optical_centroid','explicit']
    channel_h_mrad: list[float]
    channel_v_mrad: list[float]

    @model_validator(mode='after')
    def valid(self):
        if self.trajectory!='static' and self.mechanical_end_mrad<=self.mechanical_start_mrad:
            raise ValueError('Moving trajectory requires increasing mechanical endpoints')
        if self.optical_multiplier==0:
            raise ValueError('Mechanical-to-optical multiplier must be nonzero')
        if self.angle_bin_max_mrad<=self.angle_bin_min_mrad:
            raise ValueError('Scan angle bin boundaries must increase')
        return self


class SceneMotion(StrictConfig):
    range_gradient_m_per_rad: float
    radial_velocity_m_s: float = Field(gt=-C,lt=C)

"""C column-program configuration; optics and detector domains are shared with B."""
from functools import cached_property
from typing import Literal
import math
from pydantic import Field,model_validator
from ..spad.config import StrictConfig
from ..experiments.system_config import BSystemConfig
from ..experiments.scanning import ScanAcquisition
from ..configuration import read_yaml
from ..curves import merge_config
from .config import ScanSettings,ScanTiming,SceneMotion
from .planning import SystemTargets,uniform_column_budget


class PulseSpec(StrictConfig):
    time_offset_ns: float = Field(ge=0)
    energy_nj: float | None = Field(ge=0)


class ExposureSpec(StrictConfig):
    gate_mode: Literal['per_pulse','column']
    pulses: list[PulseSpec]
    tail_fraction: float = Field(ge=0,le=1)
    tail_tau_ns: float | None = Field(gt=0)

    @model_validator(mode='after')
    def valid(self):
        if any(b.time_offset_ns<=a.time_offset_ns for a,b in zip(self.pulses,self.pulses[1:])):
            raise ValueError('Pulse list times must be strictly increasing; no automatic reordering')
        if self.tail_fraction>0 and self.tail_tau_ns is None:
            raise ValueError('A nonzero tail fraction requires an explicit tail_tau_ns')
        return self


class TransportSpec(StrictConfig):
    enabled: bool
    buffer_count: int = Field(ge=1,strict=True)
    dsp_time_us: float | None = Field(ge=0)
    dsp_mode: Literal['serial','pipeline']
    dsp_initiation_us: float | None = Field(gt=0)
    mipi_mode: Literal['duration','payload']
    mipi_time_us: float | None = Field(ge=0)
    point_bytes: int | None = Field(gt=0,strict=True)
    payload_format: Literal['points','histogram','events']
    histogram_count_bits: int | None = Field(gt=0,strict=True)
    event_record_bytes: int | None = Field(gt=0,strict=True)
    column_header_bytes: int | None = Field(ge=0,strict=True)
    mipi_net_mbps: float | None = Field(gt=0)
    overflow_policy: Literal['drop_column','error']

    @model_validator(mode='after')
    def valid(self):
        if self.enabled:
            if self.dsp_time_us is None:raise ValueError('DSP time is required when transport is enabled')
            if self.dsp_mode=='pipeline' and self.dsp_initiation_us is None:raise ValueError('Pipelined DSP requires a column initiation interval')
            if self.mipi_mode=='duration' and self.mipi_time_us is None:raise ValueError('MIPI time is required in duration mode')
            if self.mipi_mode=='payload':
                format_width={'points':self.point_bytes,'histogram':self.histogram_count_bits,'events':self.event_record_bytes}[self.payload_format]
                if any(x is None for x in (format_width,self.column_header_bytes,self.mipi_net_mbps)):
                    raise ValueError('Payload mode requires format width, column header bytes and net MIPI rate')
        return self


class ColumnAcquisition(ScanAcquisition):
    frame_count: int = Field(ge=1,strict=True)
    scope_mode: Literal['frame','columns']
    scope_first_column: int = Field(ge=0,strict=True)
    scope_column_count: int = Field(ge=1,strict=True)
    analysis_bin_ps: float | None = Field(gt=0)
    trial_count: int = Field(ge=1,strict=True)
    noise_trial_count: int = Field(ge=0,strict=True)

    @model_validator(mode='after')
    def valid(self):
        # The legacy scalar period is not the column program's reference clock.
        close=self.gate_start_ns+self.gate_width_ns
        if not math.isfinite(close) or close<=self.gate_start_ns:
            raise ValueError('Gate endpoint is not representable at the requested origin/width')
        return self


class ColumnTiming(ScanTiming):
    @model_validator(mode='after')
    def valid(self):return self


class TraceSelection(StrictConfig):
    pixel_id: int | None = Field(ge=0,strict=True)
    start_ns: float | None
    end_ns: float | None

    @model_validator(mode='after')
    def valid(self):
        if self.start_ns is not None and self.end_ns is not None and self.end_ns<=self.start_ns:
            raise ValueError('Trace window end must exceed its start')
        return self


class ColumnMotion(StrictConfig):
    trajectory: Literal['sawtooth','triangle','sinusoidal','static']
    optical_multiplier: float
    optical_offset_mrad: float
    phase_offset_ns: float
    laser_time_offset_ns: float
    laser_jitter_std_ns: float = Field(ge=0)
    encoder_latency_ns: float
    encoder_angle_offset_mrad: float
    rx_scan_scale: float
    rx_angle_offset_mrad: float
    channel_direction_mode: Literal['optical_centroid','explicit']
    channel_h_mrad: list[float]
    channel_v_mrad: list[float]


class ColumnScanSettings(ScanSettings):
    active_fraction: float = Field(gt=0,le=1)


class ColumnConfig(BSystemConfig):
    acquisition: ColumnAcquisition
    system_targets: SystemTargets
    motion: ColumnMotion
    scene_motion: SceneMotion
    exposure: ExposureSpec
    transport: TransportSpec
    diagnostics: TraceSelection

    @model_validator(mode='after')
    def valid(self):
        self.validate_spatial_domains()
        return self

    @cached_property
    def budget(self):return uniform_column_budget(self.system_targets)

    @cached_property
    def scan(self):
        v=self.motion.model_dump();g=v['optical_multiplier']
        if g<=0:raise ValueError('Column scan requires a positive mechanical-to-optical multiplier')
        span=self.budget['hfov_mrad'];center=v['optical_offset_mrad']
        return ColumnScanSettings.model_validate({**v,'frame_rate_hz':self.system_targets.frame_rate_hz,
            'frame_count':self.acquisition.frame_count,'active_fraction':self.system_targets.scan_time_utilization,
            'mechanical_start_mrad':-span/(2*g),'mechanical_end_mrad':span/(2*g),
            'emission_policy':'active_only','reconstruct_flyback':False,
            'angle_bin_min_mrad':center-span/2,'angle_bin_max_mrad':center+span/2,
            'angle_bin_width_mrad':self.budget['angle_per_slot_mrad']})

    @cached_property
    def timing(self):
        return ColumnTiming.model_validate({k:getattr(self.acquisition,k) for k in ScanTiming.model_fields})

    @property
    def analysis_bin_ps(self):
        return self.readout.tdc_bin_ps if self.acquisition.analysis_bin_ps is None else self.acquisition.analysis_bin_ps

    @model_validator(mode='after')
    def column_valid(self):
        if self.system_targets.scan_time_utilization==1 and self.motion.trajectory=='sawtooth':
            raise ValueError('Sawtooth requires nonzero return time; choose a compatible trajectory or utilization below 100%')
        self.scan
        if any(p.time_offset_ns>=self.budget['slot_target_ns'] for p in self.exposure.pulses):
            raise ValueError('Pulse centers must lie in [0, T_slot); edit the list or high-level targets')
        channels=self.spad.channels_h*self.spad.channels_v
        if self.motion.channel_direction_mode=='explicit' and (len(self.motion.channel_h_mrad)!=channels or len(self.motion.channel_v_mrad)!=channels):
            raise ValueError('Direction calibration must provide one H/V pair per channel')
        ratio=self.analysis_bin_ps/self.readout.tdc_bin_ps
        if ratio<1 or not math.isclose(ratio,round(ratio),rel_tol=0,abs_tol=math.ulp(ratio)):
            raise ValueError('Analysis bin must be an integer multiple of the hardware TDC bin')
        if self.diagnostics.pixel_id is not None and self.diagnostics.pixel_id>=channels*self.device.spads_per_channel:
            raise ValueError('Trace selection contains an unknown physical SPAD pixel')
        if self.acquisition.scope_mode=='columns' and self.acquisition.scope_first_column+self.acquisition.scope_column_count>self.system_targets.slot_count*self.acquisition.frame_count:
            raise ValueError('Selected acquisition column interval exceeds the global plan')
        return self


def column_defaults():
    from ..experiments.configuration import experiment_defaults
    base=experiment_defaults('scan');legacy_scan=base.pop('scan')
    base['acquisition']['frame_count']=legacy_scan['frame_count']
    base['motion']={k:legacy_scan[k] for k in ColumnMotion.model_fields}
    sections=read_yaml('defaults.yaml')['experiments']
    base['system_targets']=sections['system_targets']
    return merge_config(base,sections['columns'])


def resolve_columns(overrides,algorithms):
    from ..legacy_config import migrate_psf_axes
    from ..numerics.spatial_profiles import validate_profile_orders
    defaults=column_defaults();ColumnConfig.model_validate(defaults)
    cfg=ColumnConfig.model_validate(merge_config(defaults,migrate_psf_axes(overrides)))
    validate_profile_orders(cfg.optics,algorithms)
    if cfg.acquisition.frame_count>algorithms.max_scan_frames:raise ValueError('Column frame count exceeds configured limit')
    if cfg.transport.buffer_count>algorithms.max_column_count:raise ValueError('Buffer count exceeds configured planner capacity')
    if cfg.system_targets.slot_count*cfg.acquisition.frame_count>algorithms.max_column_count:raise ValueError('Column count exceeds configured limit')
    pulses=cfg.system_targets.slot_count*cfg.acquisition.frame_count*len(cfg.exposure.pulses)
    if pulses>algorithms.max_column_pulses:raise ValueError('Pulse list exceeds max_column_pulses')
    if max(cfg.acquisition.trial_count,cfg.acquisition.noise_trial_count)>algorithms.max_monte_carlo_trials:
        raise ValueError('Column repeat count exceeds configured trial limit')
    bins=math.ceil((cfg.timing.gate_start_ns+cfg.timing.gate_width_ns)/(cfg.analysis_bin_ps*1e-3))+1
    if cfg.spad.channels_h*cfg.spad.channels_v*cfg.device.spads_per_channel>algorithms.max_lab_pixels:
        raise ValueError('Pixel count exceeds configured resource limit')
    if cfg.rx.rx_model=='dataset' or cfg.tx.tx_model=='dataset':
        from ..adapters.optical_data import validate_dataset
        data=validate_dataset(cfg.rx.dataset,algorithms)
        if cfg.rx.rx_model=='dataset' and (len(data.rx.x_edges_um)!=cfg.spad.channels_h*cfg.spad.H_binning+1 or
                                          len(data.rx.y_edges_um)!=cfg.spad.channels_v*cfg.spad.V_binning+1):
            raise ValueError('Imported Rx pixel geometry does not match H/V channels and binning')
    return cfg

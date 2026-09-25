"""Experiment-specific composition; defaults are exclusively read from YAML."""
from typing import Literal
import numpy as np
from pydantic import Field, model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import CurveSpec, merge_config
from ..configuration import default_values, read_yaml, Algorithms


class TimingConfig(StrictConfig):
    period_ns: float = Field(gt=0)
    gate_start_ns: float = Field(ge=0)
    gate_width_ns: float = Field(gt=0)
    laser_shots: int = Field(ge=1, strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.gate_start_ns + self.gate_width_ns > self.period_ns:
            raise ValueError('Acquisition gate exceeds period')
        return self


class LabIllumination(StrictConfig):
    wavelength_nm: float = Field(gt=0)
    signal_photons_per_pulse: float = Field(ge=0)
    background_photons_per_second_per_pixel: float = Field(ge=0)
    pulse_shape: Literal['gaussian', 'rectangular']
    pulse_fwhm_ps: float = Field(gt=0)
    pulse_delay_ns: float
    spatial_mode: Literal['uniform', 'weights']
    pixel_weights: list[float]

    @model_validator(mode='after')
    def valid(self):
        if any(not np.isfinite(x) or x < 0 for x in self.pixel_weights):
            raise ValueError('Pixel weights must be finite and nonnegative')
        if self.spatial_mode == 'weights' and (not self.pixel_weights or sum(self.pixel_weights) <= 0):
            raise ValueError('Weighted illumination requires positive total weight')
        return self


class DetectorSpectra(StrictConfig):
    pde: CurveSpec

    @model_validator(mode='after')
    def valid(self):
        p = self.pde
        if p.mode == 'standard' or p.basic.amplitude > 1 or any(x.value > 1 for x in p.csv_points+p.manual_points):
            raise ValueError('PDE must be a probability curve; standard mode is solar-only')
        return self


class LabConfig(StrictConfig):
    device: DeviceConfig
    readout: ReadoutConfig
    timing: TimingConfig
    illumination: LabIllumination
    spectral_inputs: DetectorSpectra
    rng_seed: int = Field(ge=0, strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.readout.readout_mode == 'analytic_reference':
            raise ValueError('Event research requires a digital readout mode; analytic_reference remains available in A')
        if self.readout.readout_mode.startswith('coincidence') and self.readout.coincidence_threshold > self.device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds H_binning × V_binning')
        if self.illumination.spatial_mode == 'weights' and len(self.illumination.pixel_weights) != self.device.spads_per_channel:
            raise ValueError('Pixel weights must match H_binning × V_binning')
        if self.illumination.pulse_fwhm_ps * 1e-3 >= self.timing.period_ns:
            raise ValueError('Pulse width must be shorter than period')
        return self


def experiment_defaults(kind):
    if kind not in ('spad','system','scan'):
        raise ValueError(f'Unknown experiment kind: {kind}')
    base = default_values()
    sections = read_yaml('defaults.yaml')['experiments']
    if kind not in sections:
        raise ValueError(f'Unknown experiment kind: {kind}')
    if kind=='system':
        from .system_config import domain_defaults
        return domain_defaults(base,sections[kind])
    if kind=='scan':
        result=experiment_defaults('system')
        result['acquisition'].pop('laser_shots')
        result['acquisition'].pop('monte_carlo_trials')
        return merge_config(result,sections[kind])
    # Reuse named existing defaults, never copy numeric fallbacks into domain code.
    result = {
        'device': {k: base[k] for k in DeviceConfig.model_fields},
        'readout': {k: base[k] for k in ReadoutConfig.model_fields},
        'timing': {'period_ns': 1e9/base['laser_prf_hz'], **{k: base[k] for k in TimingConfig.model_fields if k != 'period_ns'}},
        'spectral_inputs': {'pde': base['spectral_inputs']['pde']},
        'rng_seed': base['rng_seed'],
    }
    if kind == 'spad':
        result['illumination'] = {k: base[k] for k in ('wavelength_nm', 'pulse_shape', 'pulse_fwhm_ps')}
    else:
        from .spatial import system_defaults
        result.update(system_defaults(base))
    return merge_config(result, sections[kind])


def resolve_experiment(kind, overrides, algorithms=None):
    a = algorithms if algorithms is not None else Algorithms.load()
    model = LabConfig
    if kind != 'spad':
        from .spatial import SystemConfig
        model = SystemConfig
    if kind=='system':
        from .system_config import BSystemConfig
        model=BSystemConfig
    if kind=='scan':
        from .scanning import ScanConfig
        model=ScanConfig
    defaults = experiment_defaults(kind)
    model.model_validate(defaults)  # Missing/unknown default keys fail even if user overrides could fill them.
    from ..legacy_config import migrate_experiment_overrides
    cfg = model.model_validate(merge_config(defaults, migrate_experiment_overrides(kind,overrides)))
    if kind=='system' and cfg.acquisition.monte_carlo_trials>a.max_monte_carlo_trials:
        raise ValueError('Repeat count exceeds max_monte_carlo_trials')
    pixels = cfg.device.spads_per_channel
    if kind in ('system','scan'):
        pixels *= cfg.optics.channels_h * cfg.optics.channels_v
        if cfg.optics.tx_model=='dataset' or cfg.optics.rx_model=='dataset':
            from ..adapters.optical_data import validate_dataset
            data=validate_dataset(cfg.optics.dataset,a)
            if cfg.optics.rx_model=='dataset' and (len(data.rx.x_edges_um)!=cfg.optics.channels_h*cfg.device.H_binning+1 or
                                                 len(data.rx.y_edges_um)!=cfg.optics.channels_v*cfg.device.V_binning+1):
                raise ValueError('Dataset pixel geometry does not match the selected array')
    if pixels > a.max_lab_pixels or cfg.device.spads_per_channel > a.max_spads_per_channel:
        raise ValueError('Physical pixel count exceeds configured resource limit')
    if kind=='scan':
        from ..scan.schedule import scan_dimensions
        from ..scan.trajectory import angle_bin_edges
        _,_,shots=scan_dimensions(cfg,a)
        edges=angle_bin_edges(cfg.scan,a.max_scan_angle_bins)
        bins=int(np.ceil(cfg.timing.gate_width_ns*1000/cfg.readout.tdc_bin_ps))
        channels=pixels//cfg.device.spads_per_channel
        if cfg.scan.frame_count*(len(edges)-1)*channels*bins>a.max_scan_histogram_cells:
            raise ValueError('Frame × angle × channel histograms exceed max_scan_histogram_cells')
    else:
        shots=cfg.timing.laser_shots
    warmup=0 if kind=='system' and a.b_initial_condition=='fully_recovered' else a.readout_warmup_cycles
    if shots > a.max_laser_shots or shots+warmup > a.max_readout_cycles:
        raise ValueError('Acquisition cycles exceed configured resource limit')
    if np.ceil(cfg.timing.gate_width_ns*1000/cfg.readout.tdc_bin_ps) > a.max_histogram_bins:
        raise ValueError('Histogram exceeds configured resource limit')
    if cfg.readout.tdc_count > a.max_spads_per_channel:
        raise ValueError('TDC count exceeds configured resource limit')
    channels=pixels//cfg.device.spads_per_channel
    if channels*np.ceil(cfg.timing.gate_width_ns*1000/cfg.readout.tdc_bin_ps)>a.max_lab_histogram_cells:
        raise ValueError('Combined channel histograms exceed max_lab_histogram_cells')
    if pixels*(shots+warmup)>a.max_detector_sampling_work:
        raise ValueError('Pixel-cycle sampling work exceeds max_detector_sampling_work')
    return cfg

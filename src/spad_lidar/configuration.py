"""Read editable YAML from the source checkout, without caching defaults."""
from pathlib import Path
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from typing import Literal

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
_SNAPSHOT = ContextVar('configuration_snapshot', default=None)


@contextmanager
def frozen_yaml(snapshot):
    token = _SNAPSHOT.set(snapshot)
    try:
        yield
    finally:
        _SNAPSHOT.reset(token)


def yaml_snapshot():
    return {path.name: read_yaml(path.name) for path in CONFIG_DIR.glob('*.yaml')}


class ConfigurationError(RuntimeError):
    """An editable project configuration file is missing or malformed."""


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def parse_yaml(text):
    result = yaml.load(text, Loader=UniqueSafeLoader)
    if not isinstance(result, dict):
        raise ValueError("YAML root must be a mapping")
    return result


def read_yaml(name):
    snapshot = _SNAPSHOT.get()
    if snapshot is not None:
        if name not in snapshot:
            raise ConfigurationError(f'Configuration snapshot lacks {name}')
        return deepcopy(snapshot[name])
    try:
        return parse_yaml((CONFIG_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"config/{name}: {exc}") from exc


def default_values():
    doc = read_yaml("defaults.yaml")
    if set(doc) != {"schema_version", "simulation", "experiments"} or doc["schema_version"] != 1:
        raise ValueError("defaults.yaml requires schema_version: 1, simulation and experiments")
    if not isinstance(doc["simulation"], dict):
        raise ValueError("simulation must be a mapping")
    from .numerics.curves import SpectralInputs
    SpectralInputs.model_validate(doc['simulation']['spectral_inputs'])
    return doc["simulation"]


class Algorithms(BaseModel):
    @model_validator(mode='after')
    def budget_reference_limits(self):
        if self.budget_reference_min_range_m>=self.budget_reference_max_range_m:raise ValueError('Invalid default reference range')
        if self.budget_reference_points>self.budget_reference_max_points:raise ValueError('Default reference points exceed limit')
        return self

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    budget_max_histogram_bins: int = Field(ge=1)
    budget_max_channels: int = Field(ge=1)
    budget_max_physical_pixels: int = Field(ge=1)
    budget_reference_min_range_m: float = Field(gt=0)
    budget_reference_max_range_m: float = Field(gt=0)
    budget_reference_points: int = Field(ge=3)
    budget_reference_max_points: int = Field(ge=3)
    budget_reference_sigma_extent: float = Field(ge=6,le=20)
    budget_reference_max_bins: int = Field(ge=10)
    budget_reference_max_measurements: int = Field(ge=1)
    budget_timeline_max_pulses: int = Field(ge=1)
    budget_temporal_plot_samples: int = Field(ge=21,le=2001)
    budget_pulse_plot_half_widths: float = Field(gt=.5,le=20)
    budget_frame_preview_slots: int = Field(ge=2,le=32)
    budget_pipeline_preview_slots: int = Field(ge=1,le=3)
    budget_pipeline_frames: int = Field(ge=3,le=10)
    budget_output_fifo_columns: int = Field(ge=1)
    budget_pipeline_max_work: int = Field(ge=1)
    budget_schematic_max_cells: int = Field(ge=1)
    budget_schematic_scan_samples: int = Field(ge=3,le=1000)
    background_angular_domain: Literal['independent_rx', 'legacy_tx']
    filter_leakage_domain: Literal['source_coverage']
    factorize_achromatic_leakage: bool
    max_column_projection_work: int = Field(gt=0)
    max_column_pulses: int = Field(gt=0)
    max_column_count: int = Field(gt=0)
    max_column_histogram_work: int = Field(gt=0)
    max_column_selected_histogram_cells: int = Field(gt=0)
    max_column_sampling_work: int = Field(gt=0)
    column_projection_cache_entries: int = Field(ge=0)
    max_column_analysis_events: int = Field(gt=0)
    max_column_analysis_candidates: int = Field(gt=0)
    max_column_reference_work: int = Field(gt=0)
    column_result_cache_entries: int = Field(ge=0)
    parameter_preview_debounce_ms: int = Field(ge=0)
    max_visible_channels: int = Field(ge=1)
    b_mechanism_preview_gates: int = Field(ge=1)
    b_timeline_max_points: int = Field(ge=1)
    b_view_cache_entries: int = Field(ge=0)
    max_lab_analysis_events: int = Field(gt=0)
    b_initial_condition: Literal['fully_recovered', 'periodic_history']
    b_noise_reference: Literal['candidate_scalar', 'sampled_output_mean']
    max_lab_analysis_histogram_cells: int = Field(gt=0)
    max_lab_reference_cells: int = Field(gt=0)
    max_channel_ratio_cells: int = Field(gt=0)
    lab_analysis_seed_streams: dict[str,int]

    @model_validator(mode='after')
    def validate_analysis_streams(self):
        streams=self.lab_analysis_seed_streams
        if set(streams)!={'trials','noise'} or any(type(v) is not int or v<0 for v in streams.values()) or len(set(streams.values()))!=2:
            raise ValueError('lab_analysis_seed_streams requires distinct nonnegative trials/noise stream IDs')
        return self
    max_histogram_bins: int = Field(gt=0)
    max_spads_per_channel: int = Field(gt=0)
    max_laser_shots: int = Field(gt=0)
    max_monte_carlo_trials: int = Field(ge=0)
    max_line_channels: int = Field(ge=2)
    estimator_min_sigma_bins: float = Field(gt=0)
    estimator_kernel_sigma: float = Field(gt=0)
    estimator_centroid_sigma: float = Field(gt=0)
    snr_baseline_floor_counts: float = Field(gt=0)
    success_tolerance_m: float = Field(gt=0)
    sweep_min_range_m: float = Field(gt=0)
    sweep_low_ratio: float = Field(gt=0, le=1)
    sweep_high_ratio: float = Field(ge=1)
    sweep_gate_margin_ratio: float = Field(gt=0, le=1)
    sweep_points: int = Field(ge=2, le=1000)
    sweep_noise_width_sigma: float = Field(gt=0)
    pulse_preview_points: int = Field(ge=3, le=10000)
    pulse_preview_half_widths: float = Field(gt=0)
    filter_plot_padding_fraction: float = Field(gt=0)
    filter_plot_samples: int = Field(ge=2, le=10000)
    spectral_quadrature_order: int = Field(ge=6, le=32)
    spectral_plot_min_nm: float = Field(gt=0)
    spectral_plot_max_nm: float = Field(gt=0)
    spectral_plot_samples: int = Field(ge=2, le=10000)
    readout_expected_trials: int = Field(ge=1, le=1000)
    detector_calibration_trials: int = Field(ge=1, le=10000)
    detector_null_trials: int = Field(ge=1, le=10000)
    probability_confidence_level: float = Field(gt=0, lt=1)
    max_detection_bin_work: int = Field(ge=1)
    max_performance_sweep_points: int = Field(ge=1, le=100)
    max_performance_sweep_work: int = Field(ge=1)
    max_performance_sweep_bin_work: int = Field(ge=1)
    performance_sweep_range_values: list[float]
    performance_sweep_lux_values: list[float]
    performance_sweep_shot_values: list[int]
    histogram_preview_subdivisions: int = Field(ge=2, le=128)
    max_histogram_preview_bins: int = Field(ge=2, le=1000000)
    ground_truth_plot_points: int = Field(ge=101, le=10000)
    ground_truth_extent_sigma: float = Field(ge=4, le=12)
    readout_warmup_cycles: int = Field(ge=0)
    readout_trace_events: int = Field(ge=0, le=10000)
    max_readout_events_per_run: int = Field(gt=0)
    max_readout_expected_work: int = Field(gt=0)
    max_readout_cycles: int = Field(gt=0)
    basic_gaussian_extent_fwhm: float = Field(ge=4, le=12)
    basic_quadrature_segments: int = Field(ge=16, le=256)
    max_lab_pixels: int = Field(gt=0)
    max_optical_cells: int = Field(gt=0)
    spatial_angle_samples_h: int = Field(ge=2)
    max_super_gaussian_order: float = Field(ge=1)
    psf_preview_samples: int = Field(ge=5)
    psf_preview_extent_sigma: float = Field(gt=0)
    psf_preview_retained_fraction: float = Field(gt=0,le=1)
    spatial_angle_samples_v: int = Field(ge=2)
    acquisition_block_cycles: int = Field(ge=1)
    max_pending_jobs: int = Field(ge=1)
    max_job_workers: int = Field(ge=1)
    job_poll_ms: int = Field(ge=100)
    max_spatial_angle_mrad: float = Field(gt=0)
    energy_conservation_rtol: float = Field(gt=0, lt=1)
    spatial_wavelength_chunk_size: int = Field(ge=1)
    max_spatial_integration_work: int = Field(gt=0)
    max_lab_histogram_cells: int = Field(gt=0)
    max_detector_sampling_work: int = Field(gt=0)
    rx_angle_samples_h: int = Field(ge=2)
    rx_angle_samples_v: int = Field(ge=2)
    max_scan_frames: int = Field(ge=1)
    max_scan_pulses: int = Field(ge=1)
    max_scan_angle_bins: int = Field(ge=1)
    max_scan_histogram_cells: int = Field(ge=1)
    max_scan_projection_work: int = Field(ge=1)
    max_scan_sampling_work: int = Field(ge=1)
    scan_preview_table_rows: int = Field(ge=1,le=10000)
    scan_angle_boundary_tolerance_mrad: float = Field(ge=0)

    @classmethod
    def load(cls):
        return cls.model_validate(read_yaml("algorithms.yaml"))

    @classmethod
    def from_snapshot(cls, values):
        """Explicit compatibility for added UI/B-analysis policies only.

        Existing numerical policies are never replaced or silently filled.
        Historical C replays do not use the newly introduced B-analysis policies.
        """
        additions=('budget_max_channels','budget_max_physical_pixels','budget_output_fifo_columns','budget_pipeline_preview_slots','budget_pipeline_frames','budget_pipeline_max_work','budget_max_histogram_bins','budget_reference_min_range_m','budget_reference_max_range_m','budget_reference_points','budget_reference_max_points','budget_reference_sigma_extent','budget_reference_max_bins','budget_reference_max_measurements','budget_temporal_plot_samples','budget_pulse_plot_half_widths','budget_frame_preview_slots','budget_schematic_scan_samples','budget_schematic_max_cells','budget_timeline_max_pulses','parameter_preview_debounce_ms','max_visible_channels','max_lab_analysis_events',
                   'b_mechanism_preview_gates','b_timeline_max_points','b_view_cache_entries',
                   'max_lab_analysis_histogram_cells','max_lab_reference_cells','max_channel_ratio_cells',
                   'lab_analysis_seed_streams','max_column_projection_work','max_column_pulses',
                   'max_column_count','max_column_histogram_work','max_column_selected_histogram_cells',
                   'max_column_sampling_work','column_projection_cache_entries','max_column_analysis_events',
                   'max_column_reference_work','max_column_analysis_candidates','column_result_cache_entries',
                   'max_super_gaussian_order','psf_preview_samples','psf_preview_extent_sigma','psf_preview_retained_fraction',
                   'filter_leakage_domain','factorize_achromatic_leakage')
        current=read_yaml('algorithms.yaml')
        merged=dict(values)
        # Explicit historical semantics, not current numerical defaults. Old B
        # snapshots had periodic warmup and sampled laser-off output references.
        merged.setdefault('b_initial_condition','periodic_history')
        merged.setdefault('b_noise_reference','sampled_output_mean')
        merged.setdefault('background_angular_domain','legacy_tx')
        for key in additions:
            if key not in merged:merged[key]=current[key]
        return cls.model_validate(merged)

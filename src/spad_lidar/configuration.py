"""Read editable YAML from the source checkout, without caching defaults."""
from pathlib import Path
import yaml
from pydantic import BaseModel, ConfigDict, Field

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


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
    try:
        return parse_yaml((CONFIG_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"config/{name}: {exc}") from exc


def default_values():
    doc = read_yaml("defaults.yaml")
    if set(doc) != {"schema_version", "simulation"} or doc["schema_version"] != 1:
        raise ValueError("defaults.yaml requires schema_version: 1 and simulation")
    if not isinstance(doc["simulation"], dict):
        raise ValueError("simulation must be a mapping")
    return doc["simulation"]


class Algorithms(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
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

    @classmethod
    def load(cls):
        return cls.model_validate(read_yaml("algorithms.yaml"))

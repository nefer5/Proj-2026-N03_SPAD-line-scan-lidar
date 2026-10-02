"""Validated hardware-output assumptions and ideal range-reference requests."""
from typing import Literal
from pydantic import Field,model_validator
from .spad.config import StrictConfig


class BudgetTransportSpec(StrictConfig):
    """Budget payload declaration; C's event/readout transport remains separate."""
    payload_format: Literal['points','histogram','echo']
    histogram_count_bits: int | None = Field(gt=0,strict=True)
    point_bytes: int | None = Field(gt=0,strict=True)
    column_header_bytes: int | None = Field(ge=0,strict=True)
    mipi_net_mbps: float | None = Field(gt=0)


class ElectricalBudgetConfig(StrictConfig):
    capacity_mode: Literal['lanes','aggregate_net']
    channels_per_chip: int = Field(ge=1,strict=True)
    chips_per_link: int = Field(ge=1,strict=True)
    data_lanes_per_link: int = Field(ge=1,le=64,strict=True)
    lane_rate_mbps: float | None = Field(gt=0)
    payload_efficiency: float | None = Field(gt=0,le=1)
    available_links: int | None = Field(ge=1,strict=True)
    chip_header_bytes: int = Field(ge=0,strict=True)
    histogram_mode: Literal['accumulated_column','per_shot']
    ready_delay_us: float | None = Field(ge=0)
    buffer_architecture: Literal['fixed_ab','single']
    handoff_policy: Literal['acquisition_end','slot_end']
    hist_copy_us: float | None = Field(gt=0,strict=True)
    bank_clear_us: float | None = Field(ge=0)
    dsp_time_us: float | None = Field(ge=0)
    mipi_pack_us: float | None = Field(ge=0)
    echo_max_count: int = Field(ge=1,strict=True)
    echo_max_bins: int = Field(ge=1,strict=True)
    echo_descriptor_bytes: int = Field(ge=0,strict=True)
    packet_payload_bytes: int = Field(ge=1,le=65535,strict=True)
    line_short_packets: bool
    burst_gap_us: float = Field(ge=0)


class RangeMeasurement(StrictConfig):
    distance_m: float = Field(gt=0)
    area_counts: float | None = Field(ge=0)
    peak_counts: float | None = Field(ge=0)
    fwhm_ns: float | None = Field(gt=0)
    range_std_mm: float | None = Field(ge=0)
    range_bias_mm: float | None


class RangeReferenceConfig(StrictConfig):
    enabled: bool
    min_range_m: float | None = Field(gt=0)
    max_range_m: float | None = Field(gt=0)
    points: int | None = Field(ge=3,strict=True)
    measurement_mode: Literal['manual','csv']
    area_kind: Literal['signal','total']
    manual_points: list[RangeMeasurement]
    csv_points: list[RangeMeasurement]
    csv_name: str

    @model_validator(mode='after')
    def range_order(self):
        if self.min_range_m is not None and self.max_range_m is not None and self.max_range_m<=self.min_range_m:
            raise ValueError('Reference maximum range must exceed minimum range')
        return self

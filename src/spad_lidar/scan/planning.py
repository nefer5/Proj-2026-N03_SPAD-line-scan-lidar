"""High-level system requirements and their uniform column budget.

Requirements are independent of an executable scan or detector experiment.
No optical field, laser PRF or processing latency is silently changed here.
"""
import math
from pydantic import Field
from ..spad.config import StrictConfig
from ..configuration import read_yaml
from ..curves import merge_config


class SystemTargets(StrictConfig):
    frame_rate_hz: float = Field(gt=0)
    hfov_deg: float = Field(gt=0,lt=180)
    scan_time_utilization: float = Field(gt=0,le=1)
    slot_count: int = Field(ge=1,strict=True)


def resolve_system_targets(overrides):
    values=read_yaml('defaults.yaml')['experiments']['system_targets']
    SystemTargets.model_validate(values)
    return SystemTargets.model_validate(merge_config(values,overrides))


def uniform_column_budget(targets):
    frame_ns=1e9/targets.frame_rate_hz
    scan_ns=frame_ns*targets.scan_time_utilization
    slot_ns=scan_ns/targets.slot_count
    hfov_mrad=math.radians(targets.hfov_deg)*1000
    result={'frame_period_ns':frame_ns,'scan_allocatable_ns':scan_ns,
            'non_scan_ns':frame_ns-scan_ns,'slot_max_ns':slot_ns,'slot_target_ns':slot_ns,
            'angle_per_slot_mrad':hfov_mrad/targets.slot_count,
            'angle_per_slot_deg':targets.hfov_deg/targets.slot_count,
            'hfov_deg':targets.hfov_deg,'hfov_mrad':hfov_mrad,
            'required_average_optical_rad_s':hfov_mrad*1e6/scan_ns}
    if not all(math.isfinite(v) for v in result.values()) or slot_ns<=0:
        raise ValueError('System budget is not representable as finite positive column time')
    return result

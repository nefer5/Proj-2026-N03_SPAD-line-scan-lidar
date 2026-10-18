"""Periodic acquisition fields, independent of experiment composition."""
from pydantic import Field, model_validator
from ..spad.config import StrictConfig


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


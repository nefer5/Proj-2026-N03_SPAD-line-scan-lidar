"""SPAD line-scanning LiDAR system model."""

from .models import SimulationConfig
from .simulator import simulate

__all__ = ["SimulationConfig", "simulate"]


"""SPAD line-scanning LiDAR system model."""

__all__ = ["SimulationConfig", "simulate"]


def __getattr__(name):
    if name == 'SimulationConfig':
        from .models import SimulationConfig
        return SimulationConfig
    if name == 'simulate':
        from .simulator import simulate
        return simulate
    raise AttributeError(name)

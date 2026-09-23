"""Synthetic radial range field; exact constant radial-velocity interception."""
import numpy as np
from ..constants import C


def reflection_range(optics,motion,world_h_mrad,emission_time_ns):
    at_emission=optics.range_m+motion.range_gradient_m_per_rad*np.asarray(world_h_mrad)*1e-3+motion.radial_velocity_m_s*emission_time_ns*1e-9
    distance=at_emission/(1-motion.radial_velocity_m_s/C)
    if np.any(distance<=0) or not np.all(np.isfinite(distance)):
        raise ValueError('Synthetic scene has nonpositive or nonfinite reflection range')
    return distance

"""Compatibility facade; numerical curve evaluation is shared by all domains."""
from .numerics.curves import Point, BasicCurve, CurveSpec, SpectralInputs, merge_config
from .numerics.curves import Curve as NumericCurve
from .configuration import Algorithms

class Curve(NumericCurve):
    def knots(self,algorithms=None):
        return super().knots(algorithms if algorithms is not None else Algorithms.load())

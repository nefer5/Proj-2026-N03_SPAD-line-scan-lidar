"""Filter adapter over the shared spectral input model."""
from .curves import Curve


class FilterResponse(Curve):
    def __init__(self, cfg):
        super().__init__(cfg.spectral_inputs.filter)

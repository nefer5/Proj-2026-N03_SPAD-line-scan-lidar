"""Compatibility facade. Physical and application code lives in domain packages."""
from .rx.budget import Budget, aperture_area, _filter_properties, photon_budget
from .spad.analytical import _first_photon_probabilities, _sample_histogram
from .experiments.a_signal import timing_sigma_ns, _time_axis, _signal_shape, _signal_pdf, _histogram_components, expected_histogram, _preview_edges
from .processing.ranging import _estimate_range
from .processing.statistics import histogram_sample_range
from .experiments.legacy_diagnostics import crosstalk_model, _range_sweep
from .reporting.a_view import derived_quantities, filter_profile, signal_ground_truth
from .experiments.single_channel import simulate

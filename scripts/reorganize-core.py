"""One-time, auditable AST-based extraction of the existing A implementation."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'spad_lidar'
source = (ROOT / 'simulator.py').read_text(encoding='utf-8')
tree = ast.parse(source)
nodes = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
lines = source.splitlines(keepends=True)


def extract(names):
    return '\n\n'.join(''.join(lines[min([n.lineno]+[d.lineno for d in n.decorator_list])-1:n.end_lineno])
                       for n in (nodes[name] for name in names)) + '\n'


def write(path, text):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    init = target.parent / '__init__.py'
    if not init.exists():
        init.write_text('', encoding='utf-8')
    target.write_text(text, encoding='utf-8')


common = 'import numpy as np\nfrom math import pi, sqrt\nfrom ..constants import C, H, FWHM_TO_SIGMA\n'
parts = {
    'rx/budget.py': ('Budget aperture_area _filter_properties photon_budget',
                     common+'from dataclasses import dataclass\nfrom ..models import SimulationConfig\nfrom ..filters import FilterResponse\nfrom ..spectra import spectral_components\nfrom ..spad.device.response import effective_pde\n'),
    'spad/analytical.py': ('_first_photon_probabilities _sample_histogram', 'import numpy as np\n'),
    'experiments/a_signal.py': ('timing_sigma_ns _time_axis _signal_shape _signal_pdf _histogram_components expected_histogram _preview_edges',
                              common+'from scipy.special import ndtr\nfrom ..rx.budget import photon_budget\nfrom ..spad.analytical import _first_photon_probabilities\n'),
    'processing/ranging.py': ('_estimate_range', common+'from scipy.signal import convolve\nfrom ..configuration import Algorithms\nfrom ..experiments.a_signal import timing_sigma_ns\n'),
    'processing/statistics.py': ('histogram_sample_range', 'import numpy as np\n'),
    'experiments/legacy_diagnostics.py': ('crosstalk_model _range_sweep', common+'from ..configuration import Algorithms\nfrom ..rx.budget import photon_budget\nfrom .a_signal import timing_sigma_ns\n'),
    'reporting/a_view.py': ('derived_quantities filter_profile signal_ground_truth',
                           common+'from ..configuration import Algorithms\nfrom ..spectra import spectral_components\nfrom ..rx.budget import photon_budget, aperture_area\nfrom ..filters import FilterResponse\nfrom ..photon_flow import build_photon_flow\nfrom ..experiments.a_signal import timing_sigma_ns, _signal_shape, _signal_pdf, _time_axis, _preview_edges\n'),
    'experiments/single_channel.py': ('simulate', common+'''from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from ..configuration import Algorithms, read_yaml
from ..models import SimulationConfig
from ..readout import event_acquisition, event_histogram
from ..detection import evaluate_detection
from ..reporting.a_view import derived_quantities, signal_ground_truth
from .a_signal import _histogram_components
from .legacy_diagnostics import crosstalk_model, _range_sweep
from ..spad.analytical import _sample_histogram
from ..processing.ranging import _estimate_range
from ..processing.statistics import histogram_sample_range
'''),
}
exports = []
for path, (names, imports) in parts.items():
    body = extract(names.split())
    if path == 'rx/budget.py':
        body = body.replace('spectral["pde_at_laser"] * cfg.fill_factor', 'effective_pde(spectral["pde_at_laser"], cfg.fill_factor)')
    write(path, '"""Extracted A implementation; public compatibility exports remain at the old path."""\n'+imports+'\n\n'+body)
    module = path[:-3].replace('/', '.')
    exports.append(f'from .{module} import '+', '.join(names.split()))
write('simulator.py', '"""Compatibility facade. Physical and application code lives in domain packages."""\n'+'\n'.join(exports)+'\n')

readout = (ROOT / 'readout.py').read_text(encoding='utf-8')
tail = readout[readout.index('def event_histogram'):]
write('experiments/a_acquisition.py', '"""A source adapter preserves historical RNG ordering; routes through the shared detector core."""\nimport numpy as np\nfrom ..constants import C, FWHM_TO_SIGMA\nfrom .a_router import route_events\n\n'+tail)
write('readout.py', '"""Compatibility facade for A event acquisition."""\nfrom .experiments.a_router import route_events\nfrom .experiments.a_acquisition import event_histogram, event_acquisition, readout_work_estimate\n')
old = (ROOT / 'detection.py').read_text(encoding='utf-8')
write('processing/detection.py', old)
write('detection.py', '"""Compatibility exports."""\nfrom .processing.detection import binomial_interval, calibrate_threshold, evaluate_detection\n')
old = (ROOT / 'performance.py').read_text(encoding='utf-8')
old = old.replace('from .configuration', 'from ..configuration').replace('from .models','from ..models').replace('from .simulator','from ..simulator').replace('from .readout','from ..readout')
write('experiments/sweeps.py', old)
write('performance.py', '"""Compatibility exports."""\nfrom .experiments.sweeps import AXES, performance_sweep\n')
print('Extracted domain packages; original paths remain compatibility facades.')

import csv
from pathlib import Path
import runpy

import pytest

from spad_lidar.configuration import Algorithms, read_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.pde_data import pde_provenance
from spad_lidar.spectra import spectral_components

ROOT = Path(__file__).resolve().parents[1]
DATASET = 'van_sieleghem_2022_fig7_3p5v'


def test_default_csv_matches_reference_file():
    spec = SimulationConfig().spectral_inputs.pde
    metadata = read_yaml('pde-datasets.yaml')[DATASET]
    with (ROOT / metadata['csv_path']).open(encoding='utf-8', newline='') as stream:
        rows = [(float(row['wavelength_nm']), float(row['pde'])) for row in csv.DictReader(stream)]
    assert spec.mode == 'csv'
    assert [(p.wavelength_nm, p.value) for p in spec.csv_points] == rows
    assert len(rows) == 28
    assert [rows[0][0], rows[-1][0]] == [460, 1000]
    assert len(spec.manual_points) == 11
    assert pde_provenance(SimulationConfig())['id'] == DATASET


def test_literature_peak_and_interpolated_nir():
    cfg = SimulationConfig(wavelength_nm=905)
    data = spectral_components(cfg, Algorithms.load(), plot=False)
    assert data['pde_at_laser'] == pytest.approx(0.27407999458686033)
    assert 905 not in [p.wavelength_nm for p in cfg.spectral_inputs.pde.csv_points]
    peak = spectral_components(SimulationConfig(wavelength_nm=660), Algorithms.load(), plot=False)
    assert peak['pde_at_laser'] == pytest.approx(0.6637)


def test_provenance_tracks_values_not_filename():
    cfg = SimulationConfig()
    cfg.spectral_inputs.pde.csv_name = 'renamed.csv'
    assert pde_provenance(cfg)['id'] == DATASET
    cfg.spectral_inputs.pde.csv_points[0].value += 0.001
    assert pde_provenance(cfg) is None


def test_requested_fill_factor_is_separate_from_input_pde():
    cfg = SimulationConfig(wavelength_nm=905)
    assert cfg.fill_factor == 0.92
    data = spectral_components(cfg, Algorithms.load(), plot=False)
    assert data['effective_pde_at_laser'] == pytest.approx(data['pde_at_laser'] * 0.92)


def test_vector_extraction_reproduces_csv_when_local_source_available():
    source = ROOT / 'data/local-sources/arxiv-2203.01560v1.pdf'
    if not source.exists():
        pytest.skip('Original paper is not redistributed in the repository')
    pytest.importorskip('fitz')
    extract = runpy.run_path(str(ROOT / 'scripts/extract-paper-pde.py'))['extract']
    metadata = read_yaml('pde-datasets.yaml')[DATASET]
    csv_lines = (ROOT / metadata['csv_path']).read_text(encoding='utf-8').splitlines()
    assert extract(source, metadata) == '\n'.join(csv_lines[:metadata['points'] + 1]) + '\n'


def test_extrapolated_points_follow_recorded_tail_slope():
    from hashlib import sha256
    import json
    import numpy as np
    from spad_lidar.curves import Curve

    cfg = SimulationConfig()
    spec = cfg.spectral_inputs.pde
    points = {p.wavelength_nm: p.value for p in spec.csv_points}
    metadata = read_yaml('pde-datasets.yaml')[DATASET]
    extrapolation = metadata['extrapolation']
    left, right = extrapolation['anchor_wavelengths_nm']
    slope = (points[right] - points[left]) / (right - left)
    assert slope < 0
    for wavelength in extrapolation['estimated_wavelengths_nm']:
        assert points[wavelength] == round(points[right] + (wavelength-right)*slope, extrapolation['pde_digits'])
    original = [(float(p.wavelength_nm), float(p.value)) for p in spec.csv_points[:metadata['points']]]
    assert sha256(json.dumps(original, separators=(',', ':')).encode()).hexdigest() == metadata['digitized_points_sha256']
    curve = Curve(spec)
    values = curve(np.linspace(right, 1000, 81))
    assert np.all(np.diff(values) <= 0)
    assert np.all((values >= 0) & (values <= 1))
    assert float(curve(np.array(1000.0))) == pytest.approx(0.0835)
    assert float(curve(np.array(1001.0))) == 0

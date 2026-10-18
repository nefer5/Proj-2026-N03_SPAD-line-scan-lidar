"""Persistence contracts: real ownership, isolation, round trips, and failures."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil
import runpy

from fastapi.testclient import TestClient
import pytest

from spad_lidar import configuration, default_store as store
from spad_lidar.api import app

MIGRATE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/migrate-default-layout.py'))['migrate_text']


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    destination = tmp_path / 'config'
    shutil.copytree(configuration.CONFIG_DIR, destination)
    path = destination / 'defaults.yaml'
    path.write_text(MIGRATE(path.read_text(encoding='utf8')), encoding='utf8')
    monkeypatch.setattr(configuration, 'CONFIG_DIR', destination)
    monkeypatch.setattr(store, 'BACKUP_DIR', tmp_path / 'backups')
    return destination


def current(kind):
    return store._resolve(kind, {})


def commit(kind, value):
    plan = store.preview(kind, value)
    return store.save(kind, value, plan['revision'])


@pytest.mark.parametrize('kind,path,value,source', [
    ('a', ('range_m',), 120, 'domains.scene.range_m'),
    ('spad', ('illumination', 'signal_photons_per_pulse'), 22, 'experiments.spad.illumination.signal_photons_per_pulse'),
    ('spad', ('timing', 'period_ns'), 20000, 'domains.acquisition.laser_prf_hz'),
    ('system', ('tx', 'pulse_average_power_w'), 300, 'domains.tx.pulse_average_power_w'),
    ('columns', ('acquisition', 'trial_count'), 2, 'experiments.columns.acquisition.trial_count'),
    ('columns', ('motion', 'encoder_latency_ns'), 1, 'domains.motion.encoder_latency_ns'),
    ('columns', ('exposure', 'pulses'), [{'time_offset_ns': 1, 'energy_nj': None}], 'experiments.columns.exposure.pulses'),
    ('budget', ('system', 'tx', 'pulse_average_power_w'), 1100, 'experiments.budget.system.tx.pulse_average_power_w'),
    ('budget', ('geometry', 'vfov_deg'), 22, 'experiments.budget.geometry.vfov_deg'),
    ('budget', ('range_reference', 'points'), 31, 'experiments.budget.range_reference.points'),
])
def test_ownership_roundtrip(isolated, kind, path, value, source):
    desired = current(kind)
    node = desired
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    normalized = store._resolve(kind, desired)
    before = (isolated / 'defaults.yaml').read_bytes()
    plan = store.preview(kind, desired)
    assert source in [x['source'] for x in plan['changes']]
    assert (isolated / 'defaults.yaml').read_bytes() == before
    result = store.save(kind, desired, plan['revision'])
    assert current(kind) == normalized
    assert (Path(result['backup']) / 'defaults.yaml').read_bytes() == before
    # Unmodified annotations, including reference-plane definitions, survive.
    assert '# 全Tx角域、VCSEL出光/Tx光学前' in (isolated / 'defaults.yaml').read_text(encoding='utf8')


def test_shared_values_and_budget_override(isolated):
    before = {k: current(k) for k in store.KINDS}
    desired = deepcopy(before['system'])
    desired['scene']['range_m'] += 1
    result = commit('system', desired)
    assert {x['kind'] for x in result['affected']} == {'a', 'system', 'scan', 'columns', 'budget'}
    assert current('a')['range_m'] == desired['scene']['range_m']
    assert current('budget')['system']['scene']['range_m'] == desired['scene']['range_m']
    desired = current('system'); desired['tx']['pulse_average_power_w'] += 1
    commit('system', desired)
    assert current('budget')['system']['tx']['pulse_average_power_w'] == before['budget']['system']['tx']['pulse_average_power_w']
    assert current('columns')['tx']['pulse_average_power_w'] == desired['tx']['pulse_average_power_w']


def test_curve_modes_keep_independent_samples(isolated):
    desired = current('spad')
    original_csv = deepcopy(desired['spectral_inputs']['pde']['csv_points'])
    desired['spectral_inputs']['pde']['manual_points'] = [dict(wavelength_nm=900, value=0.2), dict(wavelength_nm=910, value=0.3)]
    # Inactive manual points are still deliberate user data, not a fallback.
    commit('spad', desired)
    pde = current('a')['spectral_inputs']['pde']
    assert pde['csv_points'] == original_csv
    assert pde['manual_points'] == desired['spectral_inputs']['pde']['manual_points']


def test_noop_and_concurrent_update(isolated):
    desired = current('a'); plan = store.preview('a', desired)
    assert store.save('a', desired, plan['revision'])['unchanged']
    assert not store.BACKUP_DIR.exists()
    desired['range_m'] += 1
    with (isolated / 'defaults.yaml').open('a', encoding='utf8') as f:
        f.write('\n# external edit\n')
    with pytest.raises(store.DefaultConflict):
        store.save('a', desired, plan['revision'])


def test_cross_platform_invalid_cannot_write(isolated):
    original = (isolated / 'defaults.yaml').read_bytes()
    desired = current('a')
    desired['readout_mode'] = 'analytic_reference'  # legal in A, rejected by event platforms.
    with pytest.raises(ValueError):
        store.preview('a', desired)
    assert (isolated / 'defaults.yaml').read_bytes() == original


@pytest.mark.parametrize('bad', [{'unknown': 1}, {'range_m': float('nan')}, {'range_m': -1}])
def test_invalid_input(isolated, bad):
    with pytest.raises(ValueError):
        store.preview('a', bad)


def test_duplicate_yaml(isolated):
    p = isolated / 'defaults.yaml'
    p.write_text(p.read_text(encoding='utf8') + '\nschema_version: 1\n', encoding='utf8')
    with pytest.raises(ValueError, match='Duplicate'):
        store.preview('a', {})


def test_frozen_jobs_not_mutated(isolated):
    snapshot = configuration.yaml_snapshot()
    desired = current('a'); desired['range_m'] += 1
    commit('a', desired)
    with configuration.frozen_yaml(snapshot):
        assert current('a')['range_m'] != desired['range_m']
        # Persistence previews use fresh files even inside a frozen job context.
        assert store.preview('a', desired)['unchanged']


def test_api_and_asset_fingerprints(isolated):
    client = TestClient(app)
    cfg = current('a'); cfg['range_m'] += 1
    original = (isolated / 'defaults.yaml').read_bytes()
    preview = client.post('/api/defaults/a/preview', json={'config': cfg})
    assert preview.status_code == 200
    body = dict(config=cfg, revision=preview.json()['revision'])
    assert client.post('/api/defaults/a/save', json=body, headers={'Origin': 'https://elsewhere.invalid'}).status_code == 403
    assert client.post('/api/defaults/a/save', json={'config': cfg}).status_code == 422
    response = client.post('/api/defaults/a/save', json=body)
    assert response.status_code == 200
    assert client.get('/api/defaults').json()['range_m'] == cfg['range_m']
    assert client.post('/api/defaults/a/save', json=body).status_code == 409
    assert (Path(response.json()['backup']) / 'defaults.yaml').read_bytes() == original
    digest = sha256(Path('web/shared/defaults.js').read_bytes()).hexdigest()
    for path in ('/', '/debug', '/spad', '/system', '/system/scan', '/system/budget'):
        page = client.get(path)
        assert page.status_code == 200, path
        assert f'/static/shared/defaults.js?v={digest}' in page.text
        assert page.headers['cache-control'] == 'no-store'

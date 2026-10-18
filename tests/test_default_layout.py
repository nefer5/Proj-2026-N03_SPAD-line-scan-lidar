"""Schema migration and the shared read/write provenance boundary."""
from copy import deepcopy
from pathlib import Path
import json
import runpy

import pytest
from spad_lidar.configuration import parse_yaml, yaml_snapshot, frozen_yaml
from spad_lidar.default_composition import compose_defaults, source_for
from spad_lidar.default_layout import normalize_layout
from spad_lidar.default_store import _resolve, KINDS

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = runpy.run_path(str(ROOT / 'scripts/migrate-default-layout.py'))


@pytest.fixture
def old():
    return parse_yaml((ROOT / 'tests/fixtures/numerical-reference-defaults.yaml').read_text(encoding='utf8'))


@pytest.mark.parametrize('kind', KINDS)
def test_v1_and_v2_public_config_and_schema_equal(old, kind):
    snapshot = yaml_snapshot()
    resolved = []
    from spad_lidar.models import SimulationConfig
    for defaults in (old, normalize_layout(old).document):
        with frozen_yaml(dict(snapshot, **{'defaults.yaml': defaults})):
            cfg = SimulationConfig() if kind == 'a' else SimulationConfig.for_experiment(kind, {})
            resolved.append(json.dumps({'config': cfg.model_dump(), 'schema': type(cfg).model_json_schema()}, sort_keys=True))
    assert resolved[0] == resolved[1]


def test_one_owner_for_shared_fields_and_specialized_budget(old):
    doc = normalize_layout(old).document
    # Numerical fixture can contain an intentional B acquisition override;
    # shared field examples are chosen with identical semantics in all views.
    paths = {'a': ('range_m',), 'system': ('scene', 'range_m'),
             'columns': ('scene', 'range_m'), 'budget': ('system', 'scene', 'range_m')}
    assert {source_for(k, p, doc).path for k, p in paths.items()} == {('domains', 'scene', 'range_m')}
    assert source_for('budget', ('system', 'tx', 'pulse_average_power_w'), doc).path == (
        'experiments', 'budget', 'system', 'tx', 'pulse_average_power_w')
    assert source_for('a', ('pulse_energy_nj',), doc).path != source_for('system', ('tx', 'pulse_average_power_w'), doc).path
    assert source_for('spad', ('timing', 'period_ns'), doc).reciprocal_period
    assert source_for('columns', ('motion', 'encoder_latency_ns'), old).path == (
        'experiments', 'scan', 'scan', 'encoder_latency_ns')


def test_old_b_snapshot_does_not_need_later_platforms_or_a_statistics(old):
    snapshot = yaml_snapshot()
    with frozen_yaml(dict(snapshot, **{'defaults.yaml': old})):
        before = _resolve('system', {})
    old['simulation'].pop('readout_mean_trials')
    old['simulation'].pop('noise_mean_trials')
    old['experiments'] = {key: old['experiments'][key] for key in ('spad', 'system')}
    with frozen_yaml(dict(snapshot, **{'defaults.yaml': old})):
        assert _resolve('system', {}) == before
        with pytest.raises(ValueError): _resolve('a', {})  # Never synthesize missing defaults.


@pytest.mark.parametrize('mutation', ['missing', 'unknown', 'group', 'a_extra', 'budget_extra', 'version'])
def test_malformed_layout_rejected(old, mutation):
    doc = normalize_layout(old).document
    if mutation == 'missing': del doc['domains']['rx']['rx_efficiency']
    elif mutation == 'unknown': doc['domains']['tx']['unknown'] = 1
    elif mutation == 'group': doc['domains']['new_domain'] = {}
    elif mutation == 'a_extra': doc['experiments']['a']['new_field'] = {}
    elif mutation == 'budget_extra': doc['experiments']['budget']['new_field'] = {}
    else: doc['schema_version'] = 999
    with pytest.raises(ValueError): normalize_layout(doc)


def test_formal_c_independent_of_legacy_schedule_and_experiment_default_builder(old, monkeypatch):
    snapshot = yaml_snapshot(); doc = normalize_layout(old).document
    with frozen_yaml(dict(snapshot, **{'defaults.yaml': doc})):
        before = _resolve('columns', {})
    doc['experiments']['scan']['scan']['frame_rate_hz'] = 'not a legacy rate'
    import spad_lidar.experiments.configuration as experiments
    monkeypatch.setattr(experiments, 'experiment_defaults', lambda *args: pytest.fail('C must compose domains directly'))
    with frozen_yaml(dict(snapshot, **{'defaults.yaml': doc})):
        assert _resolve('columns', {}) == before


def test_migration_preserves_annotations_and_is_idempotent():
    text = (ROOT / 'tests/fixtures/numerical-reference-defaults.yaml').read_text(encoding='utf8')
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith('  range_m:'))
    lines[index] += '  # audit reference plane retained'
    text = '\n'.join(lines) + '\n'
    migrated = MIGRATION['migrate_text'](text)
    assert parse_yaml(migrated) == normalize_layout(parse_yaml(text)).document
    assert MIGRATION['migrate_text'](migrated) == migrated
    assert '# audit reference plane retained' in migrated
    MIGRATION['validate_roundtrip'](text, migrated)


def test_legacy_module_aliases_point_to_shared_types():
    from spad_lidar.domains.optical_system import BSystemConfig
    from spad_lidar.experiments.system_config import BSystemConfig as old_b
    from spad_lidar.scan.config import ColumnMotion, ScanAcquisition
    from spad_lidar.scan.column_config import ColumnMotion as old_motion
    from spad_lidar.experiments.scanning import ScanAcquisition as old_acquisition
    assert BSystemConfig is old_b and ColumnMotion is old_motion and ScanAcquisition is old_acquisition


def test_dataset_overlay_can_replace_null_without_losing_source(old):
    doc = normalize_layout(old).document
    # Composition tracks data without interpreting or validating optical files.
    doc['experiments']['system']['rx'] = {'dataset': {'audit': {'label': 'test'}}}
    composed = compose_defaults('system', doc)
    assert composed.values['rx']['dataset'] == {'audit': {'label': 'test'}}
    assert composed.sources[('rx', 'dataset', 'audit', 'label')].path == (
        'experiments', 'system', 'rx', 'dataset', 'audit', 'label')

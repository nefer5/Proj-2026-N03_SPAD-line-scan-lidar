"""Explicit, reviewable writes to the existing YAML default owners.

Only changed inputs are written; inherited values stay inherited. No simulation
defaults or numeric policies are introduced here.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from threading import Lock
import uuid

import yaml
from . import configuration as configuration
from .models import SimulationConfig

KINDS = ('a', 'spad', 'system', 'scan', 'columns', 'budget')
LABELS = dict(a='A 单角', spad='独立 SPAD', system='B 光学', scan='旧扫描', columns='C 列扫描', budget='系统预算')
BACKUP_DIR = Path(__file__).resolve().parents[2] / 'artifacts' / 'defaults-backups'
_LOCK = Lock()


class DefaultConflict(ValueError):
    pass


def _get(tree, path):
    for key in path:
        if not isinstance(tree, dict) or key not in tree:
            raise KeyError(path)
        tree = tree[key]
    return tree


def _changes(old, new, path=()):
    if isinstance(old, dict) and isinstance(new, dict):
        for key in new:
            yield from _changes(old.get(key), new[key], path + (key,))
    elif old != new:
        yield path, old, new


def _resolve(kind, values):
    if kind == 'a':
        return SimulationConfig.model_validate(values).model_dump()
    return SimulationConfig.for_experiment(kind, values, configuration.Algorithms.load()).model_dump()


def _owner(doc, kind, path):
    """Follow the exact overlay order used by the existing default composers."""
    if kind == 'a':
        return ('simulation',) + path, False
    if kind == 'budget' and path[0] != 'system':
        section = {'targets': 'system_targets', 'assumptions': 'budget',
                   'transport': 'budget_transport', 'geometry': 'budget_geometry',
                   'rx_channel': 'budget_rx_channel', 'electrical': 'budget_electrical',
                   'range_reference': 'budget_range_reference'}[path[0]]
        return ('experiments', section) + path[1:], False
    if kind == 'budget':
        path = path[1:]
    if kind == 'columns' and path[0] == 'system_targets':
        return ('experiments', 'system_targets') + path[1:], False
    group, *rest = path
    inverse_period = group in ('timing', 'acquisition') and rest == ['period_ns']
    if group == 'spectral_inputs':
        candidates = [('simulation',) + path]
    elif group == 'rng_seed':
        candidates = [('simulation', 'rng_seed')]
    elif inverse_period:
        candidates = [('simulation', 'laser_prf_hz')]
    elif rest:
        candidates = [('simulation',) + tuple(rest)]
    else:
        candidates = []
    if kind == 'spad':
        candidates.append(('experiments', 'spad') + path)
    else:
        candidates.append(('experiments', 'system') + path)
        if kind in ('scan', 'columns'):
            if kind == 'columns' and group == 'motion':
                candidates.append(('experiments', 'scan', 'scan') + tuple(rest))
            if kind == 'columns' and path == ('acquisition', 'frame_count'):
                candidates.append(('experiments', 'scan', 'scan', 'frame_count'))
            candidates.append(('experiments', 'scan') + path)
        if kind == 'columns':
            candidates.append(('experiments', 'columns') + path)
        if kind == 'budget':
            candidates.append(('experiments', 'budget_system') + path)
    for owner in reversed(candidates):
        try:
            _get(doc, owner)
            return owner, inverse_period and owner == ('simulation', 'laser_prf_hz')
        except KeyError:
            pass
    raise ValueError('找不到默认值归属：' + '.'.join(path))


def _patch_yaml(text, updates):
    """Replace existing value spans, preserving all other YAML and comments."""
    nodes = {}

    def walk(node, path=()):
        nodes[path] = node
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                walk(value, path + (key.value,))

    walk(yaml.compose(text, Loader=configuration.UniqueSafeLoader))
    spans = []
    for path, value in updates.items():
        node = nodes[path]
        # JSON flow values are valid YAML and avoid multiline indentation changes.
        rendered = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if isinstance(node, (yaml.SequenceNode, yaml.MappingNode)) and not node.flow_style:
            # YAML permits an indentless block sequence, but a flow value on
            # the following line must be indented deeper than its owning key.
            rendered = '  ' + rendered + '\n' + ' ' * node.end_mark.column
        spans.append((node.start_mark.index, node.end_mark.index, rendered))
    for start, end, rendered in sorted(spans, reverse=True):
        text = text[:start] + rendered + text[end:]
    return text


def _snapshot():
    # Read disk directly, never a worker's frozen job configuration.
    raw = {p.name: p.read_bytes() for p in configuration.CONFIG_DIR.glob('*.yaml')}
    digest = sha256()
    for name, value in sorted(raw.items()):
        digest.update(name.encode() + b'\0' + value + b'\0')
    return raw, {k: configuration.parse_yaml(v.decode('utf-8-sig')) for k, v in raw.items()}, digest.hexdigest()


def _prepare(kind, values, expected=None):
    if kind not in KINDS:
        raise ValueError('未知平台')
    raw, snapshot, revision = _snapshot()
    if expected is not None and expected != revision:
        raise DefaultConflict('默认配置已被其他操作修改，请重新预览后保存。')
    doc = snapshot['defaults.yaml']
    with configuration.frozen_yaml(snapshot):
        before = {k: _resolve(k, {}) for k in KINDS}
        desired = _resolve(kind, values)
    updates, entries = {}, []
    for path, old, value in _changes(before[kind], desired):
        # Budget angle domains are derived from VFOV/width/channel geometry.
        if kind == 'budget' and path[0] == 'system' and path[1] in ('tx', 'rx') and path[-1] in (
            'angle_h_min_mrad', 'angle_h_max_mrad', 'angle_v_min_mrad', 'angle_v_max_mrad',
            'rx_angle_h_min_mrad', 'rx_angle_h_max_mrad', 'rx_angle_v_min_mrad', 'rx_angle_v_max_mrad'):
            continue
        owner, inverse = _owner(doc, kind, path)
        stored = 1e9 / value if inverse else value  # ns ↔ Hz unit conversion.
        if owner in updates and updates[owner] != stored:
            raise ValueError('同一默认值收到冲突输入：' + '.'.join(owner))
        updates[owner] = stored
        entries.append(dict(parameter='.'.join(path), before=old, after=value, source='.'.join(owner)))
    candidate_text = _patch_yaml(raw['defaults.yaml'].decode('utf-8-sig'), updates)
    candidate = deepcopy(snapshot)
    candidate['defaults.yaml'] = configuration.parse_yaml(candidate_text)
    with configuration.frozen_yaml(candidate):
        after = {k: _resolve(k, {}) for k in KINDS}
    # Catch ownership mistakes and unintended derived edits before touching disk.
    def equivalent(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
        if isinstance(a, float) and isinstance(b, (int, float)):
            return a == b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0)
        return a == b
    if not equivalent(after[kind], desired):
        raise ValueError('保存后无法精确恢复本页配置；请检查派生参数与继承关系。')
    affected = [dict(kind=k, label=LABELS[k], count=len(list(_changes(before[k], after[k]))))
                for k in KINDS if before[k] != after[k]]
    result = dict(revision=revision, changes=entries, affected=affected,
                  path='config/defaults.yaml', unchanged=not updates)
    return result, candidate_text.encode('utf-8'), raw['defaults.yaml']


def preview(kind, values):
    return _prepare(kind, values)[0]


@contextmanager
def _writer_lock():
    with _LOCK, (configuration.CONFIG_DIR / '.defaults-write.lock').open('a+b') as handle:
        handle.seek(0)
        if handle.read(1) == b'':
            handle.write(b'\0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DefaultConflict('另一个进程正在保存默认配置，请稍后重试。') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def save(kind, values, expected):
    with _writer_lock():
        result, content, original = _prepare(kind, values, expected)
        if result['unchanged']:
            return result
        receipt = BACKUP_DIR / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + uuid.uuid4().hex)
        receipt.mkdir(parents=True)
        (receipt / 'defaults.yaml').write_bytes(original)
        (receipt / 'receipt.json').write_text(json.dumps({**result, 'kind': kind,
            'original_sha256': sha256(original).hexdigest(), 'saved_sha256': sha256(content).hexdigest(),
            'utc': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2), encoding='utf-8')
        # The staging file is on the same volume. Failed writes stay recoverable.
        stage = configuration.CONFIG_DIR / ('.defaults-' + uuid.uuid4().hex + '.tmp')
        with stage.open('xb') as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        if _snapshot()[2] != expected:
            raise DefaultConflict('保存期间配置发生变化，未覆盖；请重新预览。')
        os.replace(stage, configuration.CONFIG_DIR / 'defaults.yaml')
        result.update(backup=str(receipt), revision=_snapshot()[2])
        return result

"""Explicit defaults schema 1 → 2 migration; values and public schemas stay fixed.

Run --check for validation or --write to migrate with a recoverable backup.
Frozen schema-1 jobs do not need migration.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import sys
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spad_lidar import configuration
from spad_lidar.default_layout import normalize_layout
from spad_lidar.default_store import _writer_lock, _resolve, KINDS


def _yaml_nodes(text):
    found = {}

    def visit(node, path=()):
        found[path] = node
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                visit(value, path + (key.value,))

    visit(yaml.compose(text, Loader=configuration.UniqueSafeLoader))
    return found


def migrate_text(text):
    original = configuration.parse_yaml(text)
    layout = normalize_layout(original)
    if original['schema_version'] == 2:
        return text
    rendered = yaml.safe_dump(layout.document, sort_keys=False, allow_unicode=True)
    old_nodes, new_nodes = _yaml_nodes(text), _yaml_nodes(rendered)
    old_lines = text.splitlines()
    new_lines = rendered.splitlines()
    # Preserve field annotations at their moved owners (e.g. energy reference plane).
    for path, source in layout.origins.items():
        old, new = old_nodes.get(source), new_nodes.get(path)
        if old is None or new is None or not isinstance(old, yaml.ScalarNode):
            continue
        if old.end_mark.line < len(old_lines):
            suffix = old_lines[old.end_mark.line][old.end_mark.column:].strip()
            if suffix.startswith('#') and new.end_mark.line < len(new_lines):
                new_lines[new.end_mark.line] += '  ' + suffix
    comments = [line for line in old_lines if line.lstrip().startswith('#')]
    header = ['# 领域化工况默认值唯一来源（schema 2）；所有数值保持原工况。',
              '# domains 为共享定义；experiments 只保存平台专用输入/差异。',
              '# 工况JSON/YAML导入导出版本不变；历史任务可继续读取schema 1。']
    header.extend('# 原版注记：' + line.lstrip().lstrip('#').strip() for line in comments)
    return '\n'.join(header + new_lines) + '\n'


def validate_roundtrip(before, after):
    snapshot = configuration.yaml_snapshot()
    results = []
    for text in (before, after):
        candidate = dict(snapshot, **{'defaults.yaml': configuration.parse_yaml(text)})
        with configuration.frozen_yaml(candidate):
            results.append({kind: _resolve(kind, {}) for kind in KINDS})
    if json.dumps(results[0], sort_keys=True) != json.dumps(results[1], sort_keys=True):
        raise ValueError('Migration changed resolved platform defaults; refusing write')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--write', action='store_true')
    args = parser.parse_args()
    with _writer_lock():
        path = configuration.CONFIG_DIR / 'defaults.yaml'
        original = path.read_bytes()
        text = original.decode('utf-8-sig')
        migrated = migrate_text(text)
        validate_roundtrip(text, migrated)
        if migrated == text:
            print('Domain defaults schema 2 validated; no migration required.')
            return
        if args.check:
            parser.exit(1, 'Valid schema 1; run --write to migrate to domain defaults schema 2.\n')
        receipt = ROOT / 'artifacts' / 'default-layout-migrations' / uuid.uuid4().hex
        receipt.mkdir(parents=True)
        (receipt / 'defaults.yaml').write_bytes(original)
        (receipt / 'receipt.json').write_text(json.dumps(dict(
            utc=datetime.now(timezone.utc).isoformat(), original_sha256=sha256(original).hexdigest(),
            migrated_sha256=sha256(migrated.encode('utf8')).hexdigest(),
            original_schema=1, target_schema=2, resolved_defaults_equal=True), indent=2), encoding='utf8')
        stage = path.with_name('.defaults-' + uuid.uuid4().hex + '.tmp')
        with stage.open('xb') as handle:
            handle.write(migrated.encode('utf8')); handle.flush(); os.fsync(handle.fileno())
        if path.read_bytes() != original:
            raise RuntimeError('Defaults changed during migration; original left intact')
        os.replace(stage, path)
        print('Migrated schema 2; all six resolved platform defaults unchanged. Backup:', receipt)


if __name__ == '__main__':
    main()

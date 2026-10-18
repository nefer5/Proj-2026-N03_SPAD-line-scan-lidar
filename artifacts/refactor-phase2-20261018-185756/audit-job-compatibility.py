"""Compare actual stored request validation against the preserved pre-refactor code."""
from pathlib import Path
import sys
import json
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
mode = sys.argv[1]
sys.path.insert(0, str(OUT / 'baseline-source/src' if mode == 'before' else ROOT / 'src'))
from spad_lidar.configuration import frozen_yaml
from spad_lidar.default_store import _resolve
results = {}
for path in sorted((ROOT / 'artifacts/runs').glob('*/request.json')):
    document = json.loads(path.read_text(encoding='utf8'))
    if not document.get('yaml'):
        continue
    try:
        with frozen_yaml(document['yaml']):
            value = _resolve(document['kind'], document.get('experiment', {}))
        results[path.parent.name] = dict(ok=True, config=value)
    except Exception as exc:
        results[path.parent.name] = dict(ok=False, error_type=type(exc).__name__)
(OUT / f'job-{mode}.json').write_text(json.dumps(results, ensure_ascii=False), encoding='utf8')
print(mode, 'requests:', len(results), 'valid:', sum(x['ok'] for x in results.values()))
if mode == 'after':
    before = json.loads((OUT / 'job-before.json').read_text(encoding='utf8'))
    regressed = [key for key, value in before.items() if value['ok'] and results.get(key) != value]
    receipt = dict(checked=len(before), previously_valid=sum(x['ok'] for x in before.values()),
                   previously_invalid=sum(not x['ok'] for x in before.values()), regressed=regressed,
                   note='Pre-existing invalid snapshots remain unsupported; missing defaults are never synthesized.')
    (OUT / 'job-compatibility.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps(receipt)); assert not regressed

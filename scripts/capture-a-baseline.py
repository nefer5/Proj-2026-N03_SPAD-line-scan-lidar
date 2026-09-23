"""Save/compare deterministic A fixtures without timestamps or mutable provenance."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import simulate
from spad_lidar.configuration import read_yaml


def capture():
    result = {}
    for mode in read_yaml('readout-modes.yaml'):
        cfg = SimulationConfig(readout_mode=mode)
        run = simulate(cfg, debug=True)
        result[mode] = {key: run[key] for key in ('budget', 'histogram', 'metrics', 'detection', 'readout')}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    actual = capture()
    if args.check:
        expected = json.loads(args.path.read_text(encoding='utf-8'))
        assert actual == expected, 'A fixture changed; inspect physics, RNG and boundary conventions'
        print('All 8 A modes: exact fixture equality (budgets, histograms, metrics, detection, readout).')
    else:
        args.path.write_text(json.dumps(actual, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        print(f'Captured {len(actual)} modes: {args.path}')

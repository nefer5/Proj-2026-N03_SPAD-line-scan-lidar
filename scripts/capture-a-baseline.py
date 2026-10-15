"""Save/compare deterministic A fixtures without timestamps or mutable provenance."""
import argparse
import json
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import simulate
from spad_lidar.configuration import read_yaml


def capture(fixture_config=None):
    result = {}
    for mode in read_yaml('readout-modes.yaml'):
        # Freeze the historical detector-enabled baseline after A retires detection.
        inputs = SimulationConfig(detection_enabled=True, monte_carlo_trials=40,
                                  readout_mean_trials=24, noise_mean_trials=24).model_dump() if fixture_config is None else fixture_config
        cfg = SimulationConfig.model_validate({**inputs, 'readout_mode':mode})
        run = simulate(cfg, debug=True)
        result[mode] = {key: run[key] for key in ('budget', 'histogram', 'metrics', 'detection', 'readout')}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config_path = args.path.with_name('fixture-config.json')
    fixture_config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else None
    actual = capture(fixture_config)
    if args.check:
        expected = json.loads(gzip.decompress(args.path.read_bytes()).decode('utf-8')) if args.path.suffix=='.gz' else json.loads(args.path.read_text(encoding='utf-8'))
        # These audit fields were added after the original fixture; compare all original values.
        for mode in actual:
            for key in ('noise_mean_trials', 'work_estimate'):
                if key not in expected[mode]['readout']:
                    actual[mode]['readout'].pop(key, None)
        assert actual == expected, 'A fixture changed; inspect physics, RNG and boundary conventions'
        print('All 8 A modes: exact fixture equality (budgets, histograms, metrics, detection, readout).')
    else:
        payload=json.dumps(actual, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
        args.path.write_bytes(gzip.compress(payload,mtime=0) if args.path.suffix=='.gz' else payload)
        print(f'Captured {len(actual)} modes: {args.path}')

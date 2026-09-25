"""Freeze real B records and a fresh YAML optical preview for UI review.

Usage: python scripts/build-b-channel-preview.py --job-id <existing B job>
No acquisition is launched and no simulation default is copied into the UI.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.reporting.readout_layout import readout_layout
from spad_lidar.webapi.labs import system_preview, system_result_view


def compact(view, label, kind, job_id=None):
    layout = readout_layout(view['optics'])
    groups = view['optics']['pixel_group_ids']
    photons = view['illumination']['signal_photons_per_pixel_per_pulse']
    for channel in layout['channels']:
        channel['signal_photons_per_pulse'] = sum(value for group, value in zip(groups, photons) if group == channel['id'])
        if 'histogram' in view:
            channel['record_count'] = sum(view['histogram']['counts'][channel['id']])
    out = {'label': label, 'kind': kind, 'job_id': job_id,
           'layout': layout, 'form_configuration': view['form_configuration'],
           'configuration': view['configuration'], 'provenance': view['provenance'],
           'x_edges_um': view['x_edges_um'], 'y_edges_um': view['y_edges_um'],
           'signal_photons_per_pixel_per_pulse': photons,
           'signal_peak': max(photons),
           'focus_window_ns': view['parameter_figures']['timing']['focus_window_ns']}
    if 'histogram' in view:
        out['histogram'] = view['histogram']
        # Keep exact plot arrays, omit unused intermediate arrays. The complete
        # immutable result remains in the original job's export; no decimation.
        out['references'] = [
            {**{k: ref[k] for k in ('basis', 'reference_plane', 'counts', 'note')},
             'high_resolution': {k: ref['high_resolution'][k] for k in ('time_ns', 'counts_per_nominal_bin')}}
            for ref in view['references']] if view.get('references') else None
        stats = view.get('statistics')
        out['statistics'] = {k: stats[k] for k in ('lower', 'upper', 'noise_mean', 'trial_count', 'noise_trial_count', 'trial_seeds', 'noise_seeds', 'method', 'note')} if stats else None
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', required=True)
    args = parser.parse_args()
    result = system_result_view(args.job_id)
    defaults = system_preview(SimulationConfig.for_experiment('system', {}).model_dump())
    snapshot = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'max_visible_channels': Algorithms.load().max_visible_channels,
                'cases': [compact(result, '本次采集 · 截图工况', 'acquisition', args.job_id),
                          compact(defaults, 'YAML 默认布局 · 参数预览', 'preview')]}
    output = ROOT / 'web/prototypes/b-channel-layout'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    html = output / 'index.html'
    if html.exists():
        import re
        content = html.read_text(encoding='utf-8')
        def fingerprint(match):
            name = match[1]
            path = (ROOT / 'web' / name.removeprefix('/static/')) if name.startswith('/static/') else output / name
            return f'{name}?v={sha256(path.read_bytes()).hexdigest()[:16]}'
        content = re.sub(r'([^"\s<>]+\.(?:js|css|json))(?:\?v=[a-f0-9]+)?(?=")', fingerprint, content)
        html.write_text(content, encoding='utf-8')
    print(json.dumps({'snapshot': str(output / 'snapshot.json'), 'layouts': [v['layout']['total_channels'] for v in snapshot['cases']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()

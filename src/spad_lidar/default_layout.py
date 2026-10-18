"""Versioned default-file structure and exact source paths (no numeric values).

Schema 1 remains readable for frozen jobs and restored backups. Schema 2 is the
editable domain layout. API experiment schemas are independent of this version.
"""
from copy import deepcopy
from dataclasses import dataclass
from .spad.config import DeviceConfig, ReadoutConfig
from .domains.system import TxConfig, SceneConfig, RxConfig, SpadArrayConfig, BackgroundConfig


A_GROUPS = {
    'tx': ('wavelength_nm', 'pulse_shape', 'pulse_fwhm_ps', 'tx_efficiency'),
    'scene': ('range_m', 'target_reflectivity', 'atmospheric_one_way_transmission', 'overlap_factor'),
    'rx': ('rx_aperture_shape', 'rx_aperture_mm', 'rx_aperture_width_mm', 'rx_aperture_height_mm', 'rx_efficiency'),
    'spad': tuple(DeviceConfig.model_fields),
    'readout': tuple(ReadoutConfig.model_fields),
    'background': tuple(BackgroundConfig.model_fields),
    'acquisition': ('laser_prf_hz', 'gate_start_ns', 'gate_width_ns', 'calibration_delay_ns',
                    'laser_shots', 'monte_carlo_trials', 'rng_seed'),
}
A_ONLY = {
    'tx': ('pulse_energy_nj',),
    'rx': ('channel_ifov_h_mrad', 'channel_ifov_v_mrad'),
    'statistics': ('readout_mean_trials', 'noise_mean_trials', 'detection_enabled', 'detection_target_pfa'),
    'legacy_crosstalk': ('line_channels', 'nearest_neighbor_crosstalk', 'crosstalk_decay_channels'),
}
A_PATHS = {key: ('domains', group, key) for group, keys in A_GROUPS.items() for key in keys}
A_PATHS.update({key: ('experiments', 'a', group, key) for group, keys in A_ONLY.items() for key in keys})
A_PATHS['spectral_inputs'] = ('domains', 'spectral_inputs')
BUDGET_SECTIONS = {'system': 'budget_system', 'assumptions': 'budget',
    'transport': 'budget_transport', 'geometry': 'budget_geometry', 'rx_channel': 'budget_rx_channel',
    'electrical': 'budget_electrical', 'range_reference': 'budget_range_reference'}


def get(tree, path):
    for key in path:
        if not isinstance(tree, dict) or key not in tree:
            raise ValueError('defaults.yaml 缺少字段：' + '.'.join(path))
        tree = tree[key]
    return tree


def nodes(tree, path=()):
    yield path, tree
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield from nodes(value, path + (key,))


def _put(tree, path, value):
    for key in path[:-1]:
        tree = tree.setdefault(key, {})
    tree[path[-1]] = deepcopy(value)


@dataclass
class DefaultLayout:
    document: dict
    origins: dict

    def source(self, path):
        # Containers as well as leaves are tracked (e.g. null → optical dataset).
        for length in range(len(path), -1, -1):
            if path[:length] in self.origins:
                return self.origins[path[:length]] + path[length:]
        return path


def normalize_layout(document):
    if type(document.get('schema_version')) is not int:
        raise ValueError('defaults.yaml schema_version must be an integer')
    if document.get('schema_version') == 2:
        if set(document) != {'schema_version', 'domains', 'experiments'}:
            raise ValueError('defaults.yaml schema 2 requires domains and experiments only')
        layout = DefaultLayout(deepcopy(document), {})
    elif document.get('schema_version') == 1:
        if set(document) != {'schema_version', 'simulation', 'experiments'}:
            raise ValueError('defaults.yaml schema 1 requires simulation and experiments only')
        if not isinstance(document['simulation'], dict) or set(document['simulation']) - set(A_PATHS):
            raise ValueError('defaults.yaml simulation contains unknown fields')
        expected = set(BUDGET_SECTIONS.values()) | {'system_targets', 'columns', 'spad', 'system', 'scan', 'scan_demo'}
        if not isinstance(document['experiments'], dict) or set(document['experiments']) - expected:
            raise ValueError('defaults.yaml schema 1 contains unknown experiment groups')
        doc = {'schema_version': 2, 'domains': {}, 'experiments': {}}
        origins = {}

        def copy(old, new):
            value = get(document, old)
            _put(doc, new, value)
            for tail, _ in nodes(value):
                origins[new + tail] = old + tail

        def available(path):
            value = document
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    return False
                value = value[key]
            return True

        for field, path in A_PATHS.items():
            if field in document['simulation']:
                copy(('simulation', field), path)
        for kind in ('spad', 'system', 'columns', 'scan', 'scan_demo'):
            if kind in document['experiments']:
                copy(('experiments', kind), ('experiments', kind))
        # Lift B-only optical/array defaults into their domains. Existing B
        # overrides of common A values deliberately remain overrides.
        for group in ('tx', 'rx', 'spad'):
            for key in list(doc['experiments'].get('system', {}).get(group, {})):
                if key not in A_PATHS:
                    copy(('experiments', 'system', group, key), ('domains', group, key))
                    del doc['experiments']['system'][group][key]
            if doc['experiments'].get('system', {}).get(group) == {}:
                del doc['experiments']['system'][group]
        from .scan.config import ColumnMotion
        for key in ColumnMotion.model_fields:
            if available(('experiments', 'scan', 'scan', key)):
                copy(('experiments', 'scan', 'scan', key), ('domains', 'motion', key))
                del doc['experiments']['scan']['scan'][key]
        if available(('experiments', 'scan', 'scan', 'frame_count')):
            copy(('experiments', 'scan', 'scan', 'frame_count'), ('domains', 'acquisition', 'frame_count'))
            del doc['experiments']['scan']['scan']['frame_count']
        if available(('experiments', 'scan', 'scene_motion')):
            copy(('experiments', 'scan', 'scene_motion'), ('domains', 'scene_motion'))
            del doc['experiments']['scan']['scene_motion']
        if available(('experiments', 'system_targets')):
            copy(('experiments', 'system_targets'), ('domains', 'system_targets'))
        for key, old in BUDGET_SECTIONS.items():
            if available(('experiments', old)):
                copy(('experiments', old), ('experiments', 'budget', key))
        layout = DefaultLayout(doc, origins)
        # Old job snapshots may predate unrelated platforms/A statistics. Do not
        # invent those defaults or require them when resolving another platform.
        # Every accessed field is still required by get() and its typed model.
        return layout
    else:
        raise ValueError('Unsupported defaults.yaml schema_version; expected 1 or 2')
    _validate_layout(layout.document)
    return layout


def _validate_layout(doc):
    from .scan.config import ColumnMotion, SceneMotion
    from .scan.planning import SystemTargets
    expected = {
        'tx': set(TxConfig.model_fields), 'scene': set(SceneConfig.model_fields),
        'rx': set(RxConfig.model_fields), 'spad': set(SpadArrayConfig.model_fields),
        'readout': set(ReadoutConfig.model_fields), 'background': set(BackgroundConfig.model_fields),
        'acquisition': set(A_GROUPS['acquisition']) | {'frame_count'},
        'spectral_inputs': {'filter', 'other', 'pde', 'solar'},
        'motion': set(ColumnMotion.model_fields), 'scene_motion': set(SceneMotion.model_fields),
        'system_targets': set(SystemTargets.model_fields),
    }
    domains = get(doc, ('domains',))
    if not isinstance(domains, dict) or set(domains) != set(expected):
        raise ValueError('defaults.yaml domain groups are missing or unknown')
    for group, keys in expected.items():
        value = domains[group]
        if not isinstance(value, dict) or set(value) != keys:
            raise ValueError(f'defaults.yaml domains.{group} fields are missing or unknown')
    sections = get(doc, ('experiments',))
    if not isinstance(sections, dict) or set(sections) != {'a', 'spad', 'system', 'scan', 'columns', 'budget', 'scan_demo'}:
        raise ValueError('defaults.yaml experiment groups are missing or unknown')
    if not isinstance(sections['budget'], dict) or set(sections['budget']) != set(BUDGET_SECTIONS):
        raise ValueError('defaults.yaml budget groups are missing or unknown')
    if not isinstance(sections['a'], dict) or set(sections['a']) != set(A_ONLY):
        raise ValueError('defaults.yaml A groups are missing or unknown')
    for group, keys in A_ONLY.items():
        if not isinstance(sections['a'][group], dict) or set(sections['a'][group]) != set(keys):
            raise ValueError(f'defaults.yaml experiments.a.{group} fields are missing or unknown')

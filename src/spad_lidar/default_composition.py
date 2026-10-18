"""One default composition and provenance graph for readers and writers."""
from copy import deepcopy
from dataclasses import dataclass, field
from .default_layout import A_PATHS, get, nodes, normalize_layout
from .domains.system import (TxConfig, SceneConfig, RxConfig, SpadArrayConfig,
                             BackgroundConfig, AcquisitionConfig)
from .spad.config import DeviceConfig, ReadoutConfig
from .domains.acquisition import TimingConfig


@dataclass(frozen=True)
class DefaultSource:
    path: tuple
    reciprocal_period: bool = False


@dataclass
class ComposedDefaults:
    values: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)

    def add(self, layout, target, source, *, reciprocal=False):
        value = get(layout.document, source)
        if reciprocal:
            value = 1e9 / value  # Hz → ns; not a second numeric default.
        for tail, child in nodes(value):
            path = target + tail
            parent = self.values
            for key in path[:-1]:
                parent = parent.setdefault(key, {})
            if not isinstance(child, dict):
                parent[path[-1]] = deepcopy(child)
            else:
                if not isinstance(parent.get(path[-1]), dict):
                    parent[path[-1]] = {}
            self.sources[path] = DefaultSource(layout.source(source + tail), reciprocal)

    def remove(self, path):
        parent = self.values
        for key in path[:-1]:
            parent = parent[key]
        del parent[path[-1]]
        self.sources = {key: val for key, val in self.sources.items() if key[:len(path)] != path}

    def overlay(self, layout, section, target=()):
        value = get(layout.document, section)
        if not isinstance(value, dict):
            raise ValueError('Default overlay must be a mapping: ' + '.'.join(section))
        # Mapping overlays merge; array/null/scalar values replace as in merge_config.
        for key in value:
            self.add(layout, target + (key,), section + (key,))


def compose_defaults(kind, document=None):
    if document is None:
        from .configuration import read_yaml
        document = read_yaml('defaults.yaml')
    layout = normalize_layout(document)
    result = ComposedDefaults()
    if kind == 'a':
        for key, source in A_PATHS.items():
            result.add(layout, (key,), source)
        return result
    if kind == 'spad':
        for target, source, keys in (
            ('device', 'spad', DeviceConfig.model_fields),
            ('readout', 'readout', ReadoutConfig.model_fields),
            ('timing', 'acquisition', [k for k in TimingConfig.model_fields if k != 'period_ns']),
            ('illumination', 'tx', ('wavelength_nm', 'pulse_shape', 'pulse_fwhm_ps'))):
            for key in keys:
                result.add(layout, (target, key), ('domains', source, key))
        result.add(layout, ('timing', 'period_ns'), ('domains', 'acquisition', 'laser_prf_hz'), reciprocal=True)
        result.add(layout, ('rng_seed',), ('domains', 'acquisition', 'rng_seed'))
        result.add(layout, ('spectral_inputs', 'pde'), ('domains', 'spectral_inputs', 'pde'))
        result.overlay(layout, ('experiments', 'spad'))
        return result
    if kind not in ('system', 'scan', 'columns', 'budget'):
        raise ValueError('Unknown default composition: ' + str(kind))
    models = {'tx': TxConfig, 'scene': SceneConfig, 'rx': RxConfig,
              'spad': SpadArrayConfig, 'readout': ReadoutConfig, 'background': BackgroundConfig,
              'acquisition': AcquisitionConfig}
    for group, model in models.items():
        for key in model.model_fields:
            if key == 'period_ns' and group == 'acquisition':
                result.add(layout, (group, key), ('domains', group, 'laser_prf_hz'), reciprocal=True)
            else:
                result.add(layout, (group, key), ('domains', group, key))
    result.add(layout, ('spectral_inputs',), ('domains', 'spectral_inputs'))
    result.overlay(layout, ('experiments', 'system'))
    if kind == 'system':
        return result
    if kind == 'budget':
        system = result
        result = ComposedDefaults(values={'system': system.values}, sources={
            ('system',) + path: source for path, source in system.sources.items()})
        # Preserve the previous typed-normalization boundary, not a raw overlay.
        from .domains.optical_system import BSystemConfig
        result.values['system'] = BSystemConfig.model_validate(result.values['system']).model_dump()
        result.add(layout, ('targets',), ('domains', 'system_targets'))
        from .scan.planning import SystemTargets
        result.values['targets'] = SystemTargets.model_validate(result.values['targets']).model_dump()
        result.overlay(layout, ('experiments', 'budget'))
        return result
    result.remove(('acquisition', 'laser_shots'))
    result.remove(('acquisition', 'monte_carlo_trials'))
    result.add(layout, ('scene_motion',), ('domains', 'scene_motion'))
    if kind == 'scan':
        result.add(layout, ('scan',), ('domains', 'motion'))
        result.add(layout, ('scan', 'frame_count'), ('domains', 'acquisition', 'frame_count'))
        result.overlay(layout, ('experiments', 'scan'))
        return result
    # Formal C uses shared domains directly, without building legacy scan config.
    # Old snapshots can carry non-schedule scan overrides; keep those readable.
    for group in layout.document['experiments']['scan']:
        if group != 'scan':
            result.add(layout, (group,), ('experiments', 'scan', group))
    result.add(layout, ('motion',), ('domains', 'motion'))
    result.add(layout, ('acquisition', 'frame_count'), ('domains', 'acquisition', 'frame_count'))
    result.add(layout, ('system_targets',), ('domains', 'system_targets'))
    result.overlay(layout, ('experiments', 'columns'))
    return result


def source_for(kind, path, document):
    sources = compose_defaults(kind, document).sources
    if path not in sources:
        raise ValueError('找不到默认值归属：' + '.'.join(path))
    return sources[path]

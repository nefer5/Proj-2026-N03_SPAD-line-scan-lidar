"""Canonical B domain configuration; flat views exist only for shared legacy adapters."""
from functools import cached_property
from pydantic import model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import SpectralInputs
from ..domains.acquisition import TimingConfig
from ..domains.optical import OpticalConfig

from ..domains.system import (OPTICAL_GROUPS, optical_fields, TxConfig, SceneConfig,
    RxConfig, SpadArrayConfig, BackgroundConfig, AcquisitionConfig)


LEGACY_PATHS = {f'optics.{key}': f'{group}.{key}' for group, keys in OPTICAL_GROUPS.items() for key in keys}
LEGACY_PATHS.update({f'device.{key}': f'spad.{key}' for key in DeviceConfig.model_fields})
LEGACY_PATHS.update({f'timing.{key}': f'acquisition.{key}' for key in TimingConfig.model_fields})
LEGACY_PATHS.update({'timing.monte_carlo_trials':'acquisition.monte_carlo_trials', 'rng_seed':'acquisition.rng_seed'})


from ..domains.optical_system import BSystemConfig  # Compatibility export.


def domain_defaults(base, additions):
    """Only references to the unique YAML defaults; no physical fallback values."""
    from ..curves import merge_config
    values = {group:{key:base[key] for key in keys if key in base} for group,keys in OPTICAL_GROUPS.items()}
    values['spad'].update({key:base[key] for key in DeviceConfig.model_fields})
    values['readout'] = {key:base[key] for key in ReadoutConfig.model_fields}
    values['acquisition'].update({key:base[key] for key in TimingConfig.model_fields if key!='period_ns'})
    values['acquisition'].update(period_ns=1e9/base['laser_prf_hz'],rng_seed=base['rng_seed'],monte_carlo_trials=base['monte_carlo_trials'])
    values['spectral_inputs'] = base['spectral_inputs']
    return merge_config(values,additions)


def form_values(cfg):
    """Bindings for existing shared widgets, never an alternative config store."""
    values={'device':cfg.device.model_dump(),'readout':cfg.readout.model_dump(),
            'timing':cfg.timing.model_dump(),'optics':cfg.optics.model_dump(),
            'spectral_inputs':cfg.spectral_inputs.model_dump(),'rng_seed':cfg.rng_seed}
    if isinstance(cfg,BSystemConfig) and hasattr(cfg.acquisition,'monte_carlo_trials'):
        values['timing']['monte_carlo_trials']=cfg.acquisition.monte_carlo_trials
    for name in ('scan','scene_motion'):
        if hasattr(cfg,name):values[name]=getattr(cfg,name).model_dump()
    return values

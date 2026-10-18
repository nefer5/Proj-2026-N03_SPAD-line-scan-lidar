"""Standalone SPAD experiment; the same runner is used for spatial illumination."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import numpy as np
from ..contracts import SensorIllumination
from ..curves import Curve
from ..spad.source import sample_candidates
from ..timing import periodic_program
from ..acquisition.adapters.periodic import acquire_candidates  # Compatibility export.
from .. import __version__


def lab_illumination(cfg):
    n = cfg.device.spads_per_channel
    source = cfg.illumination
    weights = np.ones(n) if source.spatial_mode == 'uniform' else np.array(source.pixel_weights)
    weights = weights/weights.sum()
    return SensorIllumination(np.array([source.wavelength_nm]),
        (source.signal_photons_per_pulse*weights)[:, None],
        np.full((n, 1), source.background_photons_per_second_per_pixel),
        source.pulse_shape, source.pulse_fwhm_ps, source.pulse_delay_ns,
        {'kind': 'direct_detector_illumination', 'reference_plane': 'full_pixel_before_PDE_FF'})


def run_illumination(cfg, a, light, pixel_groups, progress, cancelled, *, program=None):
    timing = cfg.timing
    if program is None:
        program = periodic_program(timing.period_ns, timing.gate_start_ns, timing.gate_width_ns,
                                   -a.readout_warmup_cycles, timing.laser_shots, timing.laser_shots)
    streams = np.random.SeedSequence(cfg.rng_seed).spawn(2)
    candidates, source_audit = sample_candidates(light, cfg.device, Curve(cfg.spectral_inputs.pde), program,
                                                 np.random.default_rng(streams[0]), a.max_readout_events_per_run)
    return acquire_candidates(cfg,a,candidates,source_audit,pixel_groups,program,streams[1],progress,cancelled)


def run_lab(cfg, a, progress, cancelled):
    light = lab_illumination(cfg)
    result = run_illumination(cfg, a, light, np.zeros(cfg.device.spads_per_channel, dtype=int), progress, cancelled)
    result['illumination'] = {'signal_photons_per_pixel_per_pulse': light.signal_photons_per_pulse.sum(axis=1).tolist(),
                              'background_photons_per_pixel_per_second': light.background_photons_per_second.sum(axis=1).tolist(),
                              'shape': [cfg.device.V_binning, cfg.device.H_binning], 'provenance': light.provenance}
    return stamp_result('SPAD_standalone', cfg, a, result)


def stamp_result(scope, cfg, a, result):
    snapshot = {'experiment': cfg.model_dump(), 'algorithms': a.model_dump()}
    result['configuration'] = snapshot
    result['provenance'] = {'scope': scope, 'model_version': __version__, 'utc': datetime.now(timezone.utc).isoformat(),
                            'configuration_sha256': sha256(json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                            'rng_seed': cfg.rng_seed, 'sampling_protocol': 'per-cycle-per-pixel-v1',
                            'limitations': ['No afterpulse or avalanche crosstalk.', 'Finite warmup, step recovery.',
                                            'Digital modes only; full event arrays exported within explicit limits.']}
    return result

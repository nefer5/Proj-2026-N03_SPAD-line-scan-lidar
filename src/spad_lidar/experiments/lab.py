"""Standalone SPAD experiment; the same runner is used for spatial illumination."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import numpy as np
from ..contracts import SensorIllumination, CandidateEvents
from ..curves import Curve
from ..spad import AcquisitionSession
from ..spad.source import sample_candidates
from ..spad.device import apply_jitter
from ..timing import periodic_program
from ..processing.records import histogram_records
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


def acquire_candidates(cfg,a,candidates,source_audit,pixel_groups,program,electronic_seed,progress,cancelled):
    """Shared state evolution, electronics response and quantized recording for B/C."""
    timing=cfg.timing
    if cancelled():
        raise InterruptedError('Cancelled before event acquisition')
    from ..spad.acquisition import evolve_program
    session=evolve_program(cfg.device,cfg.readout,pixel_groups,program,candidates,a,progress,cancelled)
    by_cycle={w.cycle:w for w in program.windows}
    records = session.readout.records
    jittered = apply_jitter(np.random.default_rng(electronic_seed), np.array([r['phase_ns'] for r in records]), cfg.readout.other_jitter_fwhm_ps)
    bin_width_ns = cfg.readout.tdc_bin_ps*1e-3
    measured = []
    for r, phase in zip(records, jittered):
        effective_close=min(timing.gate_start_ns+timing.gate_width_ns,program.windows[-1].end_ns-by_cycle[r['cycle']].start_ns)
        if timing.gate_start_ns <= phase < effective_close:
            code = int(np.floor((phase-timing.gate_start_ns)/bin_width_ns))
            left = timing.gate_start_ns+code*bin_width_ns
            right = min(left+bin_width_ns, effective_close)
            measured.append({'cycle': r['cycle'], 'channel': r['channel'], 'tdc': r['tdc'], 'tdc_code': code,
                             'phase_ns': (left+right)/2, 'interval_start_ns': left, 'interval_end_ns': right})
    histogram = histogram_records(measured, timing.gate_start_ns, timing.gate_width_ns, cfg.readout.tdc_bin_ps,
                                  int(np.max(pixel_groups))+1)
    audit = {**session.stats, 'timestamp_outside_gate_losses': len(records)-len(measured),
             'final_records': len(measured), 'source': source_audit, 'trace': session.readout.trace,
             'trace_truncated': session.stats['logic_triggers'] > len(session.readout.trace)}
    return {'records': measured, 'histogram': histogram, 'audit': audit,
            'record_schema': {'version': 1, 'time_basis': 'cycle-relative ns', 'tdc_bin_ps': cfg.readout.tdc_bin_ps,
                              'pixel_identity': 'not exported beyond hardware TDC identity',
                              'replay': 'Rebin only at integer multiples of original bin width with original gate origin.'}}


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

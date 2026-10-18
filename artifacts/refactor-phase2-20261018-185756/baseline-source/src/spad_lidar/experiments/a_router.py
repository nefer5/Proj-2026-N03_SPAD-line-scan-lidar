"""Compatibility adapter from periodic A configuration to explicit core program."""
import numpy as np
from ..contracts import CandidateEvents
from ..spad import AcquisitionSession, DeviceConfig, ReadoutConfig
from ..timing import periodic_program


def route_events(cfg, times, pixels, trace_limit=0):
    events = CandidateEvents(times, pixels)
    period = 1e9 / cfg.laser_prf_hz
    # A has no prehistory: only the requested acquisition interval can change state.
    if np.any(events.pixel_id >= cfg.spads_per_channel):
        raise ValueError('Unknown physical pixel ID')
    inside = (events.time_ns >= 0) & (events.time_ns < cfg.laser_shots*period)
    outside_count = int(np.count_nonzero(~inside))
    events = CandidateEvents(events.time_ns[inside], events.pixel_id[inside])
    program = periodic_program(period, cfg.gate_start_ns, cfg.gate_width_ns, 0, cfg.laser_shots, cfg.laser_shots)
    device = DeviceConfig(**{k: getattr(cfg, k) for k in DeviceConfig.model_fields})
    readout = ReadoutConfig(**{k: getattr(cfg, k) for k in ReadoutConfig.model_fields})
    session = AcquisitionSession(device, readout, np.zeros(device.spads_per_channel, dtype=int), program, trace_limit)
    records = session.advance(events, program.windows[-1].end_ns)
    session.stats['outside_acquisition_candidates'] = outside_count
    return np.array([r['phase_ns'] for r in records]), session.stats, session.readout.trace

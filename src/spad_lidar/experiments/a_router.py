"""Compatibility adapter from periodic A configuration to explicit core program."""
import numpy as np
from ..contracts import CandidateEvents
from ..spad import AcquisitionSession, DeviceConfig, ReadoutConfig
from ..timing import periodic_program


def route_events(cfg, times, pixels, trace_limit=0):
    events = CandidateEvents(times, pixels)
    period = 1e9 / cfg.laser_prf_hz
    first = min(0, int(np.floor(events.time_ns[0]/period))) if len(events.time_ns) else 0
    end = max(cfg.laser_shots, int(np.floor(events.time_ns[-1]/period))+1) if len(events.time_ns) else cfg.laser_shots
    program = periodic_program(period, cfg.gate_start_ns, cfg.gate_width_ns, first, end, cfg.laser_shots)
    device = DeviceConfig(**{k: getattr(cfg, k) for k in DeviceConfig.model_fields})
    readout = ReadoutConfig(**{k: getattr(cfg, k) for k in ReadoutConfig.model_fields})
    session = AcquisitionSession(device, readout, np.zeros(device.spads_per_channel, dtype=int), program, trace_limit)
    records = session.advance(events, program.windows[-1].end_ns)
    return np.array([r['phase_ns'] for r in records]), session.stats, session.readout.trace

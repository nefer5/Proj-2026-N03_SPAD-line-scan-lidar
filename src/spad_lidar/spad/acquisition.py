"""Detector session with explicit program and resumable state across time blocks."""
import numpy as np
from dataclasses import asdict
from copy import deepcopy
from ..contracts import AcquisitionProgram, AcquisitionWindow
from .config import DeviceConfig, ReadoutConfig
from .device import DeviceState
from .readout import ReadoutEngine


class AcquisitionSession:
    def __init__(self, device, readout, pixel_groups, program, trace_limit):
        groups = np.asarray(pixel_groups)
        if groups.ndim != 1 or not len(groups) or np.any(groups < 0) or np.any(groups != np.floor(groups)):
            raise ValueError('Readout topology must contain nonnegative integer group IDs')
        if not np.array_equal(np.unique(groups), np.arange(int(groups.max())+1)):
            raise ValueError('Readout group IDs must be contiguous')
        if np.any(np.bincount(groups.astype(int)) != device.spads_per_channel):
            raise ValueError('Each readout group must contain H_binning × V_binning physical SPADs')
        if readout.readout_mode == 'analytic_reference':
            raise ValueError('Analytic reference cannot produce event records')
        if readout.readout_mode.startswith('coincidence') and readout.coincidence_threshold > device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds group size')
        self.device_config = device
        self.program = program
        self.device = DeviceState(len(groups))
        self.stats = {k: 0 for k in ('potential_events', 'spad_dead_losses', 'outside_gate_avalanches',
                                    'avalanches', 'logic_triggers', 'tdc_dead_losses', 'capacity_losses', 'recorded')}
        self.readout = ReadoutEngine(readout, groups, self.stats, trace_limit)
        self.watermark_ns = program.windows[0].start_ns

    def advance(self, events, until_ns):
        if not np.isfinite(until_ns) or until_ns < self.watermark_ns or until_ns > self.program.windows[-1].end_ns:
            raise ValueError('Invalid block end; time cannot move backwards or exceed program')
        if len(events.time_ns) and (events.time_ns[0] < self.watermark_ns or events.time_ns[-1] >= until_ns):
            raise ValueError('Events must lie in the half-open block [watermark, until)')
        if np.any(events.pixel_id >= len(self.device.ready_ns)):
            raise ValueError('Unknown physical pixel ID')
        before = len(self.readout.records)
        cfg = self.device_config
        for t, pixel in zip(events.time_ns, events.pixel_id):
            w = self.program.locate(t)
            inside = w.gate_open_ns <= t < w.gate_close_ns
            detector_inside = w.detector_gate_open_ns <= t < w.detector_gate_close_ns
            if cfg.detector_operation == 'gated' and not detector_inside:
                continue
            if w.measured:
                self.stats['potential_events'] += 1
            if not self.device.avalanche(t, pixel, cfg.spad_dead_time_ns):
                if w.measured:
                    self.stats['spad_dead_losses'] += 1
                continue
            if w.measured:
                self.stats['avalanches'] += 1
            if not inside:
                if w.measured:
                    self.stats['outside_gate_avalanches'] += 1
                continue
            self.readout.avalanche(float(t), int(pixel), w)
        self.readout.flush(until_ns)
        self.watermark_ns = until_ns
        self.stats['logic_rejected_or_merged'] = self.stats['avalanches']-self.stats['outside_gate_avalanches']-self.stats['logic_triggers']
        return self.readout.records[before:]

    def checkpoint(self):
        """Portable JSON state; None represents a resource that has never fired."""
        finite = lambda values: [None if v == -np.inf else float(v) for v in values]
        r = self.readout
        return {'schema_version': 1, 'device_config': self.device_config.model_dump(),
                'readout_config': r.cfg.model_dump(), 'pixel_groups': r.pixel_groups.tolist(),
                'program': [asdict(w) for w in self.program.windows], 'trace_limit': r.trace_limit,
                'watermark_ns': self.watermark_ns, 'device_ready': finite(self.device.ready_ns),
                'tdc_ready': finite(r.ready), 'hits': r.hits.tolist(), 'capacity_cycle': list(r.capacity_cycle),
                'logic_cycle': list(r.logic_cycle), 'or_end': finite(r.or_end),
                'active': [[[int(p), float(t)] for p,t in active.items()] for active in r.active],
                'pending': [{'key': list(key), 'end_ns': v[0], 'cells': sorted(v[1]), 'cycle': v[2].cycle, 'group': v[3]}
                            for key,v in r.pending.items()],
                'stats': deepcopy(self.stats), 'records': deepcopy(r.records), 'trace': deepcopy(r.trace)}

    @classmethod
    def restore(cls, checkpoint):
        data = deepcopy(checkpoint)
        if data['schema_version'] != 1:
            raise ValueError('Unsupported acquisition checkpoint version')
        program = AcquisitionProgram(AcquisitionWindow(**w) for w in data['program'])
        s = cls(DeviceConfig.model_validate(data['device_config']), ReadoutConfig.model_validate(data['readout_config']),
                data['pixel_groups'], program, data['trace_limit'])
        if set(data) != set(s.checkpoint()):
            raise ValueError('Checkpoint fields do not match schema')
        def decode(values, length):
            arr = np.array([-np.inf if v is None else v for v in values],dtype=float)
            if arr.shape != (length,) or np.any(np.isnan(arr)) or np.any(arr == np.inf):
                raise ValueError('Invalid checkpoint state array')
            return arr
        r = s.readout
        s.device.ready_ns = decode(data['device_ready'],len(s.device.ready_ns))
        r.ready = decode(data['tdc_ready'],len(r.ready))
        r.or_end = decode(data['or_end'],r.groups)
        r.hits = np.asarray(data['hits'],dtype=int)
        if r.hits.shape != r.ready.shape or np.any(r.hits < 0):
            raise ValueError('Invalid checkpoint capacity counters')
        r.capacity_cycle, r.logic_cycle = data['capacity_cycle'], data['logic_cycle']
        r.active = [dict(items) for items in data['active']]
        if any(len(items)!=r.groups for items in (r.capacity_cycle,r.logic_cycle,r.active)):
            raise ValueError('Invalid checkpoint logic groups')
        windows = {w.cycle:w for w in program.windows}
        r.pending = {tuple(item['key']):(item['end_ns'],set(item['cells']),windows[item['cycle']],item['group']) for item in data['pending']}
        s.stats.clear();s.stats.update(data['stats'])
        r.records,r.trace = data['records'],data['trace']
        s.watermark_ns = data['watermark_ns']
        if not np.isfinite(s.watermark_ns) or not program.windows[0].start_ns <= s.watermark_ns <= program.windows[-1].end_ns:
            raise ValueError('Invalid checkpoint watermark')
        return s

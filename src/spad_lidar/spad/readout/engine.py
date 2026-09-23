"""Stateful readout logic, independent of photon generation and device recovery."""
import numpy as np


class ReadoutEngine:
    def __init__(self, config, pixel_groups, stats, trace_limit):
        self.cfg = config
        self.pixel_groups = np.asarray(pixel_groups, dtype=int)
        self.groups = int(self.pixel_groups.max()) + 1
        self.independent = config.readout_mode.startswith('independent')
        self.resources_per_group = config.tdc_count if config.readout_mode == 'shared_multitdc' else 1
        count = len(pixel_groups) if self.independent else self.groups * self.resources_per_group
        self.ready = np.full(count, -np.inf)
        self.hits = np.zeros(count, dtype=int)
        self.capacity_cycle = [None] * self.groups
        self.logic_cycle = [None] * self.groups
        self.or_end = np.full(self.groups, -np.inf)
        self.active = [dict() for _ in range(self.groups)]
        self.pending = {}
        self.stats = stats
        self.trace_limit = trace_limit
        self.trace = []
        self.records = []

    def _resources(self, group):
        if self.independent:
            return np.flatnonzero(self.pixel_groups == group).tolist()
        start = group * self.resources_per_group
        return list(range(start, start + self.resources_per_group))

    def trigger(self, t, pixel, group, window):
        if self.capacity_cycle[group] != window.cycle:
            self.hits[self._resources(group)] = 0
            self.capacity_cycle[group] = window.cycle
        if window.measured:
            self.stats['logic_triggers'] += 1
        cap = 1 if self.cfg.readout_mode.endswith('first') else self.cfg.tdc_max_hits_per_cycle
        choices = [pixel] if self.independent else self._resources(group)
        available = [i for i in choices if t >= self.ready[i] and self.hits[i] < cap]
        outcome, channel = 'recorded', None
        if not available:
            capacity = all(self.hits[i] >= cap for i in choices)
            outcome = 'capacity_loss' if capacity else 'tdc_dead_loss'
            if window.measured:
                self.stats['capacity_losses' if capacity else 'tdc_dead_losses'] += 1
        else:
            channel = min(available, key=lambda i: (self.ready[i], i))
            self.ready[channel] = t + self.cfg.tdc_dead_time_ns
            self.hits[channel] += 1
            if window.measured:
                self.records.append({'time_ns': float(t), 'phase_ns': float(t-window.start_ns),
                                     'cycle': window.cycle, 'channel': group, 'tdc': channel})
                self.stats['recorded'] += 1
        if window.measured and len(self.trace) < self.trace_limit:
            self.trace.append({'cycle': window.cycle, 'trigger_time_ns': float(t-window.start_ns),
                               'tdc': channel, 'outcome': outcome})

    def flush(self, until_ns):
        due = sorted((value[0], key) for key, value in self.pending.items() if value[0] <= until_ns)
        for end, key in due:
            _, cells, window, group = self.pending.pop(key)
            if len(cells) >= self.cfg.coincidence_threshold:
                self.trigger(float(np.nextafter(end, -np.inf)), 0, group, window)

    def avalanche(self, t, pixel, window):
        group = int(self.pixel_groups[pixel])
        self.flush(t)
        if self.logic_cycle[group] != window.cycle and window.gate_has_gap:
            self.or_end[group] = -np.inf
            self.active[group].clear()
        self.logic_cycle[group] = window.cycle
        mode = self.cfg.readout_mode
        if self.independent:
            self.trigger(t, pixel, group, window)
        elif mode == 'coincidence_fixed':
            index = int(np.floor((t-window.gate_open_ns) / self.cfg.coincidence_window_ns))
            key = (window.cycle, group, index)
            end = min(window.gate_open_ns+(index+1)*self.cfg.coincidence_window_ns, window.gate_close_ns)
            if key not in self.pending:
                self.pending[key] = (end, set(), window, group)
            self.pending[key][1].add(pixel)
        elif mode == 'coincidence_sliding':
            active = {p: expiry for p, expiry in self.active[group].items() if expiry > t}
            before = len(active)
            active[pixel] = t + self.cfg.coincidence_window_ns
            self.active[group] = active
            if before < self.cfg.coincidence_threshold <= len(active):
                self.trigger(t, 0, group, window)
        else:
            if t >= self.or_end[group]:
                self.trigger(t, 0, group, window)
            self.or_end[group] = max(self.or_end[group], t + self.cfg.or_pulse_width_ns)

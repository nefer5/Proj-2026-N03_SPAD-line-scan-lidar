from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class AcquisitionWindow:
    cycle: int
    start_ns: float
    end_ns: float
    gate_open_ns: float
    gate_close_ns: float
    measured: bool
    detector_gate_open_ns: float
    detector_gate_close_ns: float

    @property
    def gate_has_gap(self):
        return self.gate_open_ns > self.start_ns or self.gate_close_ns < self.end_ns


class AcquisitionProgram:
    """Explicit absolute time intervals. Core has no knowledge of laser PRF."""
    def __init__(self, windows):
        self.windows = tuple(windows)
        if not self.windows:
            raise ValueError('Acquisition program must contain intervals')
        seen = set()
        for i, w in enumerate(self.windows):
            if not np.all(np.isfinite([w.start_ns, w.end_ns, w.gate_open_ns, w.gate_close_ns, w.detector_gate_open_ns, w.detector_gate_close_ns])):
                raise ValueError('Program times must be finite')
            if not w.start_ns < w.end_ns or not w.start_ns <= w.gate_open_ns <= w.gate_close_ns <= w.end_ns:
                raise ValueError('Invalid acquisition interval or gate')
            if not w.start_ns <= w.detector_gate_open_ns <= w.detector_gate_close_ns <= w.end_ns:
                raise ValueError('Invalid detector gate')
            if w.cycle in seen or (i and self.windows[i-1].end_ns > w.start_ns):
                raise ValueError('Program intervals overlap or cycle identifiers repeat')
            seen.add(w.cycle)
        self.starts = np.array([w.start_ns for w in self.windows])

    def locate(self, t):
        i = int(np.searchsorted(self.starts, t, side='right')) - 1
        if i < 0 or t >= self.windows[i].end_ns:
            raise ValueError(f'Event {t} ns lies outside acquisition program')
        return self.windows[i]


@dataclass(frozen=True)
class CandidateEvents:
    """Internal post-PDE potential avalanches; not the public optical input."""
    time_ns: np.ndarray
    pixel_id: np.ndarray

    def __post_init__(self):
        times = np.asarray(self.time_ns, dtype=float)
        raw_pixels = np.asarray(self.pixel_id)
        if times.ndim != 1 or raw_pixels.shape != times.shape or not np.all(np.isfinite(times)):
            raise ValueError('Event arrays must be finite, one dimensional and aligned')
        if not np.all(np.isfinite(raw_pixels)) or np.any(raw_pixels < 0) or np.any(raw_pixels != np.floor(raw_pixels)):
            raise ValueError('Pixel IDs must be nonnegative integers')
        order = np.argsort(times, kind='stable')
        object.__setattr__(self, 'time_ns', times[order])
        object.__setattr__(self, 'pixel_id', raw_pixels.astype(int)[order])

"""Generic gate-union acquisition program, independent of optics and scanning."""
from dataclasses import replace
import math
from ..contracts import AcquisitionProgram

def merge_intervals(intervals):
    merged=[]
    for start,end in sorted(intervals):
        if end<=start:continue
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    return merged


class GatedProgram(AcquisitionProgram):
    def __init__(self,windows,segments):
        super().__init__(windows)
        if set(segments)!={w.cycle for w in self.windows}:raise ValueError('Gate segments must match reference intervals exactly')
        for w in self.windows:
            previous=w.start_ns
            for lo,hi in segments[w.cycle]:
                if not math.isfinite(lo) or not math.isfinite(hi) or not w.start_ns<=lo<hi<=w.end_ns or lo<previous:
                    raise ValueError('Gate fragments must be finite, ordered, disjoint and inside their reference interval')
                previous=hi
        self.segments=segments

    def detector_intervals(self,window):return self.segments[window.cycle]

    def locate(self,time_ns):
        w=super().locate(time_ns)
        for lo,hi in self.segments[w.cycle]:
            if lo<=time_ns<hi:
                return replace(w,gate_open_ns=lo,gate_close_ns=hi,detector_gate_open_ns=lo,detector_gate_close_ns=hi)
        return replace(w,gate_open_ns=w.start_ns,gate_close_ns=w.start_ns,
                       detector_gate_open_ns=w.start_ns,detector_gate_close_ns=w.start_ns)



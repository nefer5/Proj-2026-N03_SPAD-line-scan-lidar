"""Bounded passive tracing of the shared device state, with no random draws."""
import numpy as np
from .state import DeviceState

class TraceDevice(DeviceState):
    def __init__(self,count,selection,program,limit):
        super().__init__(count);self.selection=selection;self.program=program;self.limit=limit;self.trace=[];self.selected_events=0

    def avalanche(self,t,pixel,dead_time_ns):
        before=self.ready_ns[pixel];accepted=super().avalanche(t,pixel,dead_time_ns)
        s=self.selection;w=self.program.locate(t)
        if w.measured and (s.pixel_id is None or s.pixel_id==pixel) and (s.start_ns is None or t>=s.start_ns) and (s.end_ns is None or t<s.end_ns):
            self.selected_events+=1
            if len(self.trace)<self.limit:self.trace.append({'time_ns':float(t),'cycle':w.cycle,'pixel_id':int(pixel),
                'outcome':'avalanche' if accepted else 'spad_dead_loss',
                'ready_before_ns':float(before) if np.isfinite(before) else None,
                'ready_after_ns':float(self.ready_ns[pixel]),'inside_recording_gate':bool(w.gate_open_ns<=t<w.gate_close_ns)})
        return accepted



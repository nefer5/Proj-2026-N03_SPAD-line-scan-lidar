"""Gate-close commands and trace metadata around the same readout core."""
import numpy as np
from .engine import ReadoutEngine

class FragmentAwareReadout(ReadoutEngine):
    """Only gate-close commands are added; shared SPAD/TDC logic is unchanged."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.last_gate=[None]*self.groups

    def avalanche(self,t,pixel,window):
        group=int(self.pixel_groups[pixel]);previous=self.last_gate[group]
        gate=(window.cycle,window.gate_open_ns,window.gate_close_ns)
        if previous is not None and previous[0]==window.cycle and previous[1:]!=gate[1:]:
            self.flush(t);self.or_end[group]=-np.inf;self.active[group].clear()
        self.last_gate[group]=gate
        super().avalanche(t,pixel,window)

    def trigger(self,t,pixel,group,window):
        index=len(self.trace);super().trigger(t,pixel,group,window)
        if len(self.trace)>index:
            row=self.trace[index];resource=row['tdc']
            row.update(group=group,absolute_time_ns=float(t),
                       ready_after_ns=float(self.ready[resource]) if resource is not None else None)



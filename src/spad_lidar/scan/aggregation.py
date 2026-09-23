"""The single pulse-count convention used by preview and reconstruction."""
import numpy as np


def count_pulses(schedule,frame_count,frame_period_ns,angle_bins):
    assigned=np.zeros((frame_count,angle_bins),dtype=int)
    true_useful=np.zeros_like(assigned);actual=np.zeros_like(assigned)
    outside_assigned=0;outside_true=0
    for row in schedule:
        actual_frame=int(np.floor(row['emission_time_ns']/frame_period_ns))
        if row['emitted'] and 0<=actual_frame<frame_count:
            b=row['true_bin']
            if b>=0:
                actual[actual_frame,b]+=1
                if row['true_useful']:true_useful[actual_frame,b]+=1
            else:outside_true+=1
        if not row['measured'] or not row['reconstruct']:continue
        f=row['frame'];b=row['assigned_bin']
        if b<0 or not 0<=f<frame_count:
            outside_assigned+=1
        else:assigned[f,b]+=1
    return {'assigned':assigned,'true_useful':true_useful,'actual':actual,
            'outside_assigned':outside_assigned,'outside_true':outside_true}

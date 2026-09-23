"""Angles in optical-ray mrad; all dynamics are computed in Python."""
import numpy as np


def mirror_pose(settings, time_ns, *, commanded=False):
    t=np.asarray(time_ns,dtype=float)
    period_ns=1e9/settings.frame_rate_hz
    phase_ns=np.remainder(t+(0 if commanded else settings.phase_offset_ns),period_ns)
    phase=phase_ns/period_ns
    start=settings.mechanical_start_mrad;span=settings.mechanical_end_mrad-start
    if settings.trajectory=='static':
        mechanical=np.full_like(t,start)
        velocity=np.zeros_like(t)
        active=np.ones_like(t,dtype=bool)
    elif settings.trajectory=='sawtooth':
        active_ns=period_ns*settings.active_fraction
        active=phase_ns<active_ns
        mechanical=start+np.where(active,span*phase_ns/active_ns,span*(period_ns-phase_ns)/(period_ns-active_ns))
        velocity=np.where(active,span/(period_ns*settings.active_fraction),-span/(period_ns*(1-settings.active_fraction)))
    elif settings.trajectory=='triangle':
        mechanical=start+span*np.where(phase<.5,2*phase,2*(1-phase))
        velocity=np.where(phase<.5,2*span/period_ns,-2*span/period_ns)
        active=np.ones_like(t,dtype=bool)
    else:
        mechanical=start+span*(1-np.cos(2*np.pi*phase))/2
        velocity=span*np.pi*np.sin(2*np.pi*phase)/period_ns
        active=np.ones_like(t,dtype=bool)
    optical=mechanical*settings.optical_multiplier+settings.optical_offset_mrad
    return mechanical,optical,velocity*settings.optical_multiplier,active


def angle_bin_edges(settings, max_bins):
    ratio=(settings.angle_bin_max_mrad-settings.angle_bin_min_mrad)/settings.angle_bin_width_mrad
    if not np.isfinite(ratio):
        raise ValueError('Scan angle span/bin width is not representable')
    count=int(np.ceil(ratio))
    if count>max_bins:
        raise ValueError('Scan angle bins exceed configured limit')
    edges=settings.angle_bin_min_mrad+np.arange(count+1)*settings.angle_bin_width_mrad
    edges[-1]=settings.angle_bin_max_mrad
    return edges


def angle_bin_index(angle, edges):
    """Every bin is [left,right), including the last; outside is explicitly -1."""
    values=np.asarray(angle)
    index=np.searchsorted(edges,values,side='right')-1
    return np.where((values>=edges[0])&(values<edges[-1]),index,-1)


def snap_angle_roundoff(values,edges,tolerance_mrad):
    """Only bin tagging is snapped; optical ray calculations retain the original values."""
    values=np.asarray(values,dtype=float)
    if tolerance_mrad>=np.min(np.diff(edges))/2:
        raise ValueError('Angle roundoff tolerance must be less than half the smallest bin')
    right=np.searchsorted(edges,values,side='left')
    lo=np.clip(right-1,0,len(edges)-1);hi=np.clip(right,0,len(edges)-1)
    closest=np.where(np.abs(values-edges[lo])<=np.abs(values-edges[hi]),edges[lo],edges[hi])
    snapped=np.where(np.abs(values-closest)<=tolerance_mrad,closest,values)
    return snapped,snapped-values

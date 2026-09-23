from dataclasses import dataclass
import numpy as np
from ..contracts import AcquisitionWindow,AcquisitionProgram
from .trajectory import mirror_pose,angle_bin_edges,angle_bin_index,snap_angle_roundoff


def scan_dimensions(cfg,a):
    frame_ns=1e9/cfg.scan.frame_rate_hz
    total_ns=frame_ns*cfg.scan.frame_count
    if not np.isfinite(total_ns) or total_ns<=0 or not np.isfinite(total_ns/cfg.timing.period_ns):
        raise ValueError('Scan duration is not representable')
    shots=int(np.ceil(total_ns/cfg.timing.period_ns))
    if shots>a.max_scan_pulses or shots+a.readout_warmup_cycles>a.max_readout_cycles:
        raise ValueError('Frame/PRF budget exceeds scan pulse resource limit')
    if cfg.scan.frame_count>a.max_scan_frames:
        raise ValueError('Frame count exceeds configured scan limit')
    if np.spacing(total_ns)>=min(cfg.readout.tdc_bin_ps,cfg.optics.pulse_fwhm_ps)*1e-3:
        raise ValueError('Float64 absolute clock cannot resolve the configured TDC/pulse width over this scan duration')
    return frame_ns,total_ns,shots


def build_schedule(cfg,a):
    frame_ns,total_ns,shots=scan_dimensions(cfg,a)
    edges=angle_bin_edges(cfg.scan,a.max_scan_angle_bins)
    cycles=np.arange(-a.readout_warmup_cycles,shots,dtype=int)
    nominal=cycles*cfg.timing.period_ns
    # Stream 2 is isolated from the existing photon/electronics streams 0 and 1.
    rng=np.random.default_rng(np.random.SeedSequence(cfg.rng_seed).spawn(3)[2])
    jitter=rng.normal(0,cfg.scan.laser_jitter_std_ns,len(cycles))
    emission=nominal+cfg.scan.laser_time_offset_ns+jitter
    mech,true_opt,velocity,true_active=mirror_pose(cfg.scan,emission)
    _,command_opt,_,command_active=mirror_pose(cfg.scan,nominal,commanded=True)
    _,encoder_opt,_,_=mirror_pose(cfg.scan,nominal-cfg.scan.encoder_latency_ns)
    encoder_opt=encoder_opt+cfg.scan.encoder_angle_offset_mrad
    emitted=np.ones(len(cycles),dtype=bool) if cfg.scan.emission_policy=='continuous' else command_active
    if np.any(np.diff(emission[emitted])<=0):
        raise ValueError('Laser timing errors reorder emitted pulses; reduce jitter or use a lower PRF')
    if not all(np.all(np.isfinite(x)) for x in (emission,mech,true_opt,velocity,command_opt,encoder_opt)):
        raise ValueError('Scan pose or timing is nonfinite')
    encoder_tag,encoder_roundoff=snap_angle_roundoff(encoder_opt,edges,a.scan_angle_boundary_tolerance_mrad)
    true_tag,true_roundoff=snap_angle_roundoff(true_opt,edges,a.scan_angle_boundary_tolerance_mrad)
    assigned=angle_bin_index(encoder_tag,edges);truth=angle_bin_index(true_tag,edges)
    rows=[];windows=[]
    for i,cycle in enumerate(cycles):
        start=float(nominal[i]);end=min(float(start+cfg.timing.period_ns),total_ns)
        requested_open=start+cfg.timing.gate_start_ns
        requested_close=requested_open+cfg.timing.gate_width_ns
        gate_open=min(requested_open,end);gate_close=min(requested_close,end)
        windows.append(AcquisitionWindow(int(cycle),start,end,gate_open,gate_close,cycle>=0,gate_open,gate_close))
        frame=int(np.floor(start/frame_ns)) if cycle>=0 else -1
        rows.append({'cycle':int(cycle),'frame':frame,'nominal_time_ns':start,'emission_time_ns':float(emission[i]),
          'laser_timing_error_ns':float(emission[i]-start),'mechanical_angle_mrad':float(mech[i]),
          'true_tx_optical_mrad':float(true_opt[i]),'command_optical_mrad':float(command_opt[i]),
          'encoder_optical_mrad':float(encoder_opt[i]),'encoder_angle_error_mrad':float(encoder_opt[i]-true_opt[i]),
          'optical_velocity_mrad_per_ns':float(velocity[i]),'command_active':bool(command_active[i]),
          'true_active':bool(true_active[i]),'emitted':bool(emitted[i]),'assigned_bin':int(assigned[i]),'true_bin':int(truth[i]),
          'encoder_bin_roundoff_mrad':float(encoder_roundoff[i]),'true_bin_roundoff_mrad':float(true_roundoff[i]),
          'reconstruct':bool(emitted[i] and (command_active[i] or cfg.scan.reconstruct_flyback)),
          'true_useful':bool(emitted[i] and (true_active[i] or cfg.scan.reconstruct_flyback)),
          'gate_open_ns':gate_open,'gate_close_ns':gate_close,
          'gate_truncation_ns':float(cfg.timing.gate_width_ns-(gate_close-gate_open)),
          'slot_end_ns':end,'measured':bool(cycle>=0)})
    return AcquisitionProgram(windows),rows,edges,{'frame_period_ns':frame_ns,'duration_ns':total_ns,'scheduled_slots':shots,
        'prf_hz':1e9/cfg.timing.period_ns,'nominal_frame_slots':frame_ns/cfg.timing.period_ns,
        'angle_boundary_tolerance_mrad':a.scan_angle_boundary_tolerance_mrad,
        'boundary_convention':'Half-open time frames, gates and angle bins. Configured near-edge numerical roundoff corrections are logged; optical angles are untouched. Final partial gate truncation is reported, never renormalized.'}

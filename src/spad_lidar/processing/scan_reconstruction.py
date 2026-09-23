"""Measurement-only angular accumulation and ranging; truth is used only after estimation."""
from types import SimpleNamespace
import numpy as np
from .records import histogram_records
from .ranging import _estimate_range
from ..scan.aggregation import count_pulses


def reconstruct_scan(cfg,a,records,schedule,angle_edges,directions,truth,bin_ps=None):
    width=cfg.readout.tdc_bin_ps if bin_ps is None else bin_ps
    template=histogram_records([],cfg.timing.gate_start_ns,cfg.timing.gate_width_ns,width,1)
    time=np.array(template['time_ns']);edges=np.array(template['edges_ns'])
    frames=cfg.scan.frame_count;bins=len(angle_edges)-1;channels=len(directions)
    if frames*bins*channels*len(time)>a.max_scan_histogram_cells:
        raise ValueError('Scan reconstruction exceeds histogram cell limit')
    cube=np.zeros((frames,bins,channels,len(time)),dtype=int)
    counts=count_pulses(schedule,frames,1e9/cfg.scan.frame_rate_hz,bins)
    assigned,true_useful,all_emitted=counts['assigned'],counts['true_useful'],counts['actual']
    encoder_sum=np.zeros((frames,bins));time_sum=np.zeros((frames,bins))
    photons=np.zeros((frames,bins,channels));range_sum=np.zeros_like(photons);h_sum=np.zeros_like(photons);v_sum=np.zeros_like(photons)
    frame_ns=1e9/cfg.scan.frame_rate_hz
    by_cycle={row['cycle']:row for row in schedule}
    measured=[row for row in schedule if row['measured']]
    outside_assigned=counts['outside_assigned'];outside_true=counts['outside_true']
    for row in schedule:
        if not row['measured'] or not row['reconstruct']:continue
        f=row['frame'];b=row['assigned_bin']
        if b<0 or not 0<=f<frames:continue
        encoder_sum[f,b]+=row['encoder_optical_mrad'];time_sum[f,b]+=row['nominal_time_ns']
        source=truth.get(row['cycle'])
        if source is not None:
            photons[f,b]+=source['photons'];range_sum[f,b]+=source['range_weighted']
            h_sum[f,b]+=source['h_weighted'];v_sum[f,b]+=source['v_weighted']
    rejected={'blanked_or_flyback':0,'outside_angle_or_frame':0,'outside_histogram':0}
    for record in records:
        row=by_cycle[record['cycle']]
        if not row['reconstruct']:
            rejected['blanked_or_flyback']+=1;continue
        f=row['frame'];b=row['assigned_bin']
        if b<0 or not 0<=f<frames:
            rejected['outside_angle_or_frame']+=1;continue
        index=int(np.searchsorted(edges,record['phase_ns'],side='right'))-1
        if not 0<=index<len(time):
            rejected['outside_histogram']+=1;continue
        cube[f,b,record['channel'],index]+=1
    known=SimpleNamespace(pulse_fwhm_ps=cfg.optics.pulse_fwhm_ps,pulse_shape=cfg.optics.pulse_shape,
        spad_jitter_fwhm_ps=cfg.device.spad_jitter_fwhm_ps,other_jitter_fwhm_ps=cfg.readout.other_jitter_fwhm_ps,
        tdc_bin_ps=width,calibration_delay_ns=cfg.optics.calibration_delay_ns)
    centers=(np.asarray(angle_edges[:-1])+np.asarray(angle_edges[1:]))/2
    rows=[];cloud=[]
    for f in range(frames):
        for b in range(bins):
            encoder=encoder_sum[f,b]/assigned[f,b] if assigned[f,b] else centers[b]
            for ch,(cal_h,cal_v) in enumerate(directions):
                count=int(cube[f,b,ch].sum())
                distance,score=_estimate_range(known,time,cube[f,b,ch],a) if count else (None,0.)
                # No truth, scene range, or actual laser jitter is passed to the estimator.
                weight=photons[f,b,ch]
                reference=float(range_sum[f,b,ch]/weight) if weight>0 else None
                true_h=float(h_sum[f,b,ch]/weight) if weight>0 else None
                true_v=float(v_sum[f,b,ch]/weight) if weight>0 else None
                report_h=float(encoder*cfg.scan.rx_scan_scale+cfg.scan.rx_angle_offset_mrad+cal_h) if cal_h is not None else None
                report_v=float(cal_v) if cal_v is not None else None
                valid_range=distance is not None and np.isfinite(distance) and distance>=0
                valid_direction=report_h is not None and report_v is not None and np.isfinite(report_h) and np.isfinite(report_v) and abs(report_h)<np.pi/2*1e3 and abs(report_v)<np.pi/2*1e3
                status=('no_range' if distance is None else 'invalid_range' if not valid_range else
                        'invalid_direction' if not valid_direction else 'unthresholded_estimate')
                row={'frame':f,'angle_bin':b,'channel':ch,'scan_bin_center_mrad':float(centers[b]),
                    'assigned_pulses':int(assigned[f,b]),'true_useful_pulses':int(true_useful[f,b]),
                    'recorded_counts':count,'raw_distance_m':distance,'peak_score':score,
                    'reported_h_mrad':report_h,'reported_v_mrad':report_v,
                    'source_weighted_range_m':reference,'source_weighted_h_mrad':true_h,'source_weighted_v_mrad':true_v,
                    'range_error_m':float(distance-reference) if distance is not None and reference is not None else None,
                    'direction_error_h_mrad':float(report_h-true_h) if report_h is not None and true_h is not None else None,
                    'status':status}
                rows.append(row)
                if valid_range and valid_direction:
                    tx=np.tan(report_h*1e-3);ty=np.tan(report_v*1e-3);norm=np.sqrt(1+tx*tx+ty*ty)
                    cloud.append({**row,'x_m':float(distance*tx/norm),'y_m':float(distance*ty/norm),'z_m':float(distance/norm)})
    errors=[r['range_error_m'] for r in rows if r['range_error_m'] is not None]
    angle_errors=[r['encoder_angle_error_mrad'] for r in measured if r['emitted']]
    mean_pulse_dwell=None
    if cfg.scan.trajectory=='sawtooth' and cfg.scan.phase_offset_ns==0 and cfg.scan.laser_time_offset_ns==0 and cfg.scan.laser_jitter_std_ns==0:
        omega=abs((cfg.scan.mechanical_end_mrad-cfg.scan.mechanical_start_mrad)*cfg.scan.optical_multiplier/(frame_ns*cfg.scan.active_fraction))
        mean_pulse_dwell=(np.diff(angle_edges)/(omega*cfg.timing.period_ns)).tolist()
    summary={'scheduled_slots':len(measured),'emitted_reference_slots':sum(r['emitted'] for r in measured),
        'blanked_slots':sum(not r['emitted'] for r in measured),'emitted_during_true_flyback':sum(r['emitted'] and not r['true_active'] for r in measured),
        'assigned_pulses':int(assigned.sum()),'true_useful_pulses':int(true_useful.sum()),
        'outside_assigned_angle':outside_assigned,'outside_true_angle':outside_true,
        'retained_records':int(cube.sum()),'excluded_records':rejected,
        'empty_angle_bins':int((assigned==0).sum()),'range_rows':len(rows),
        'rows_with_range':len([r for r in rows if r['raw_distance_m'] is not None]),
        'invalid_range_rows':sum(r['status']=='invalid_range' for r in rows),
        'invalid_direction_rows':sum(r['status']=='invalid_direction' for r in rows),
        'conditional_range_rmse_m':float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
        'max_encoder_vs_emission_error_mrad':float(np.max(np.abs(angle_errors))) if angle_errors else None,
        'gate_truncated_ns':float(sum(r['gate_truncation_ns'] for r in measured))}
    return {'assigned_pulses_per_frame_bin':assigned.tolist(),'true_useful_pulses_per_frame_bin':true_useful.tolist(),
        'actual_emissions_per_frame_bin':all_emitted.tolist(),'angle_bin_centers_mrad':centers.tolist(),
        'histogram_cube_counts':cube.tolist(),'histogram_cube_axes':['frame','scan_angle_bin','readout_channel','time_bin'],
        'histogram_time_ns':time.tolist(),'histogram_edges_ns':edges.tolist(),'processing_bin_ps':width,
        'range_rows':rows,'point_cloud':cloud,'summary':summary,'uniform_forward_dwell_reference_per_bin':mean_pulse_dwell,
        'reconstruction_note':'按触发参考时刻的编码器角标签归入半开角bin；通道方向采用显式标定或Rx光学角质心。真值仅用于误差审计，不参与测距寻峰。RMSE只统计有数值估计且有源信号参考的格点；不是Pd/PFA。负距离或超出前向坐标域的方向保留原始估计和无效标识，不输出点云。未做飞行时间内姿态补偿、多通道角融合或检测标定。'}

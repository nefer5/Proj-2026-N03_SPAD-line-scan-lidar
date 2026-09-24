"""Column accumulation uses measured reference IDs; no dense frame/time cube."""
from collections import defaultdict
from types import SimpleNamespace
import math
from decimal import Decimal,ROUND_CEILING
import numpy as np
from .ranging import _estimate_range
from ..scan.column_optics import yaw_angles


def histogram_bin_count(cfg,bin_ps):
    width=Decimal(str(bin_ps))*Decimal('0.001')
    origin=Decimal(str(cfg.timing.gate_start_ns));span=Decimal(str(cfg.timing.gate_width_ns))
    return int((span/width).to_integral_value(rounding=ROUND_CEILING))+int((origin/width).to_integral_value(rounding=ROUND_CEILING))


def histogram_edges(cfg,bin_ps):
    quantum=Decimal(str(bin_ps))*Decimal('0.001');start=Decimal(str(cfg.timing.gate_start_ns));span=Decimal(str(cfg.timing.gate_width_ns))
    width=float(quantum);origin=float(start);upper=float(start+span)
    first=-int((start/quantum).to_integral_value(rounding=ROUND_CEILING));last=int((span/quantum).to_integral_value(rounding=ROUND_CEILING))
    edges=origin+np.arange(first,last+1)*width
    edges[0]=0.;edges[-1]=upper
    return edges


def histogram_for_records(records,cfg,bin_ps,channels):
    edges=histogram_edges(cfg,bin_ps)
    counts=np.zeros((len(channels),len(edges)-1),dtype=np.int64);mapping={ch:i for i,ch in enumerate(channels)}
    if records:
        times=np.array([r['phase_ns'] for r in records]);indices=np.searchsorted(edges,times,side='right')-1
        for r,index in zip(records,indices):
            ch=mapping.get(r['channel'])
            if ch is not None and 0<=index<len(edges)-1:counts[ch,index]+=1
    return {'edges_ns':edges.tolist(),'time_ns':((edges[:-1]+edges[1:])/2).tolist(),'counts':counts.tolist(),'bin_ps':bin_ps,'channels':channels}


def reconstruct_columns(cfg,a,records,schedule,columns,directions,truth):
    by_col=defaultdict(list)
    for record in records:by_col[record['column_id']].append(record)
    by_cycle={r['cycle']:r for r in schedule};by_source=defaultdict(list)
    for r in schedule:
        if r['measured']:by_source[r['column_id']].append(r)
    channels=cfg.spad.channels_h*cfg.spad.channels_v;edges=histogram_edges(cfg,cfg.analysis_bin_ps)
    if len(columns)*channels*(len(edges)-1)>a.max_column_histogram_work:raise ValueError('Column histogram/ranging work limit exceeded')
    estimator=SimpleNamespace(pulse_fwhm_ps=cfg.tx.pulse_fwhm_ps,pulse_shape=cfg.tx.pulse_shape,
        spad_jitter_fwhm_ps=cfg.spad.spad_jitter_fwhm_ps,other_jitter_fwhm_ps=cfg.readout.other_jitter_fwhm_ps,
        tdc_bin_ps=cfg.analysis_bin_ps,calibration_delay_ns=cfg.acquisition.calibration_delay_ns)
    ranges=[];cloud=[];retained=0;count_map={};max_counts={}
    for col in columns:
        subset=by_col[col['column_id']];count_map[col['column_id']]=len(subset)
        hist=histogram_for_records(subset,cfg,cfg.analysis_bin_ps,list(range(channels)))
        time=np.array(hist['time_ns']);retained+=sum(sum(row) for row in hist['counts'])
        max_counts[col['column_id']]=max((max(row,default=0) for row in hist['counts']),default=0)
        source=by_source[col['column_id']]
        photon_sum=np.zeros(channels);range_sum=np.zeros(channels);h_sum=np.zeros(channels);v_sum=np.zeros(channels)
        for r in source:
            if r['cycle'] in truth:
                tr=truth[r['cycle']];photon_sum+=tr['photons'];range_sum+=tr['range_weighted'];h_sum+=tr['h_weighted'];v_sum+=tr['v_weighted']
        fallback=float(np.mean([r['encoder_optical_mrad'] for r in source]))
        angles=defaultdict(list)
        for r in subset:angles[r['channel']].append(by_cycle[r['cycle']]['encoder_optical_mrad'])
        for ch,(lh,lv) in enumerate(directions):
            counts=np.array(hist['counts'][ch]);distance,score=_estimate_range(estimator,time,counts,a) if counts.sum() else (None,0.)
            encoder=float(np.mean(angles[ch])) if angles[ch] else fallback
            if lh is None or lv is None:reported_h=reported_v=None
            else:
                hh,vv=yaw_angles(lh,lv,encoder*cfg.motion.rx_scan_scale+cfg.motion.rx_angle_offset_mrad)
                reported_h=float(hh);reported_v=float(vv)
            reference=float(range_sum[ch]/photon_sum[ch]) if photon_sum[ch]>0 else None
            true_h=float(h_sum[ch]/photon_sum[ch]) if photon_sum[ch]>0 else None
            valid=distance is not None and np.isfinite(distance) and distance>=0 and reported_h is not None and abs(reported_h)<np.pi/2*1e3 and abs(reported_v)<np.pi/2*1e3
            row={'column_id':col['column_id'],'frame':col['frame'],'column':col['column'],'channel':ch,
                'h_route':ch%cfg.spad.channels_h,'v_line':ch//cfg.spad.channels_h,
                'raw_distance_m':distance,'recorded_counts':int(counts.sum()),'peak_score':score,
                'reported_h_mrad':reported_h,'reported_v_mrad':reported_v,
                'source_weighted_range_m':reference,'source_weighted_h_mrad':true_h,
                'range_error_m':float(distance-reference) if distance is not None and reference is not None else None,
                'status':'unthresholded_estimate' if valid else 'no_valid_range_or_direction'}
            ranges.append(row)
            if valid:
                x=np.tan(reported_h*1e-3);y=np.tan(reported_v*1e-3);norm=np.sqrt(1+x*x+y*y)
                cloud.append({**row,'x_m':float(distance*x/norm),'y_m':float(distance*y/norm),'z_m':float(distance/norm)})
    errors=[r['range_error_m'] for r in ranges if r['range_error_m'] is not None]
    return {'range_rows':ranges,'point_cloud':cloud,'processing_bin_ps':cfg.analysis_bin_ps,
        'record_counts_by_column':dict(count_map),'histogram_peak_count_by_column':max_counts,
        'summary':{'column_count':len(columns),'range_rows':len(ranges),'points_with_raw_estimate':len(cloud),
            'retained_analysis_records':retained,'outside_analysis_window_records':len(records)-retained,
            'conditional_rmse_m':float(np.sqrt(np.mean(np.square(errors)))) if errors else None},
        'note':'Histogram phase uses measured trigger/anchor reference, never hidden photon source. Source truth is only used after estimation for audit. Full records are retained; histograms are generated per selected column/channel. Ranges and points are unthresholded, without C-specific Pd/PFA calibration or inferred-ToF pointing compensation.'}

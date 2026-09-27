"""C UI views, explicit budgets and on-demand recorded/ideal histograms."""
from types import SimpleNamespace
import hashlib,json,math
import numpy as np
from ..configuration import read_yaml
from ..models import SimulationConfig
from ..constants import C
from ..curves import Curve
from ..scan.planning import uniform_column_budget
from ..scan.column_schedule import build_column_schedule,scheduled_energy,acquisition_scope
from ..scan.column_optics import ColumnPulseProjection
from ..scan.trajectory import mirror_pose
from ..scan.transport import transport_plan
from ..experiments.spatial import project_illumination
from ..experiments.columns import noise_resource_probe
from ..experiments.lab import stamp_result
from ..spad.device import effective_pde
from ..numerics.temporal import temporal_pdf,temporal_cdf,timing_sigma_ns
from ..processing.column_reconstruction import histogram_for_records,histogram_edges,histogram_bin_count
from ..processing.ranging import _estimate_range
from .spatial_view import optical_view


def system_budget_view(targets):
    derived=uniform_column_budget(targets);ids=('c_high_level_frame','c_high_level_slot','c_high_level_angle')
    formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    values=targets.model_dump()
    return {'configuration':values,'derived':derived,'source':'config/defaults.yaml + validated system_targets overrides',
        'sha256':hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest(),
        'formulas':[{'id':i,'latex':formulas[i],'note':notes[i]} for i in ids]}


def motion_view(cfg,a,rows,column_id):
    selected=[r for r in rows if r['measured'] and r['column_id'] in (column_id,column_id+1)]
    ranges=sorted(set([*a.performance_sweep_range_values,cfg.scene.range_m]))
    output=[];previous={};table=None
    if cfg.rx.rx_model not in ('gaussian_psf','super_gaussian_psf'):
        from ..experiments.spatial import optical_dataset
        from ..rx.response import ReceiverResponse
        rx=optical_dataset(cfg,a).rx;table=ReceiverResponse(rx,cfg.optics,a)
        xc=(np.asarray(rx.x_edges_um[:-1])+rx.x_edges_um[1:])/2
    for row in selected:
        comparisons=[]
        for distance in ranges:
            flight=2*distance/C*1e9
            _,rx,_,_=mirror_pose(cfg.scan,row['emission_time_ns']+flight)
            rx=float(rx)*cfg.motion.rx_scan_scale+cfg.motion.rx_angle_offset_mrad
            relative=row['true_tx_optical_mrad']-rx
            from ..rx.spatial import image_center
            if table is None:cx=float(image_center(cfg.optics,relative,0)[0])
            else:
                _,psf=table.evaluate(cfg.tx.wavelength_nm,relative,0)
                mass=float(np.asarray(psf).sum());cx=float(np.asarray(psf).sum(axis=-2)@xc/mass) if mass>0 else None
            comparisons.append({'range_m':distance,'flight_ns':flight,'rx_axis_mrad':rx,'relative_rx_h_mrad':relative,'image_x_um':cx})
        prior=previous.get(row['column_id'])
        output.append({**row,'returns':comparisons,'mechanical_velocity_rad_s':row['optical_velocity_mrad_per_ns']*1e6/cfg.motion.optical_multiplier,
            'previous_pulse_interval_ns':None if prior is None else row['emission_time_ns']-prior['emission_time_ns'],
            'previous_pulse_shift_mrad':None if prior is None else row['true_tx_optical_mrad']-prior['true_tx_optical_mrad']})
        if row['has_pulse']:previous[row['column_id']]=row
    times=np.linspace(0,cfg.budget['frame_period_ns'],a.pulse_preview_points)
    mechanical,optical,velocity,_=mirror_pose(cfg.scan,times)
    return {'selected_rows':output,'frame_time_ns':times.tolist(),'mechanical_mrad':mechanical.tolist(),
        'optical_mrad':optical.tolist(),'optical_velocity_rad_s':(velocity*1e6).tolist(),
        'mechanical_velocity_rad_s':(velocity*1e6/cfg.motion.optical_multiplier).tolist(),
        'image_position_kind':'高斯无限像面中心' if table is None else '截获PSF质心（无响应时未定义）',
        'note':'距离对照采用静止中心射线；实际场景梯度/运动和逐角截获见脉冲审计。电子标定延迟不参与转镜飞行姿态。'}


def column_preview(cfg,a,column_id=0):
    program,rows,columns,budget=build_column_schedule(cfg,a)
    if not 0<=column_id<len(columns):raise ValueError('Unknown column selection')
    light,groups,info=project_illumination(cfg,a,lambda *args:None,lambda:False)
    view=optical_view(cfg,a,info,laser_shots=budget['emission_count'])
    view['parameter_figures'].pop('timing')
    budget.update(scheduled_energy(cfg,rows,budget['duration_ns']))
    tail=None if cfg.exposure.tail_fraction==0 else (cfg.exposure.tail_fraction,cfg.exposure.tail_tau_ns)
    half=a.pulse_preview_half_widths*cfg.tx.pulse_fwhm_ps*1e-3
    times=np.linspace(-half,half,a.pulse_preview_points)
    if tail is not None:times=np.unique(np.r_[times,np.linspace(0,a.ground_truth_extent_sigma*tail[1],a.ground_truth_plot_points)])
    power=cfg.tx.total_pulse_energy_nj*temporal_pdf(times,cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,tail)
    view['parameter_figures']['pulse'].update(series=[{'label':'继承波形 · Tx光学前','x':times.tolist(),'y':power.tolist(),'color':'cyan'}],
        x_label='相对脉冲中心 / ns',facts=[['继承单发能量',cfg.tx.total_pulse_energy_nj,'nJ'],
          ['基底FWHM',cfg.tx.pulse_fwhm_ps,'ps'],['当前帧平均输入功率',budget['tx_input_average_power_w'],'W']],
        note='继承波形供energy_nj=null的发射使用；显式单发能量按同一归一化波形缩放。拖尾是能量占比与指数延迟，不在图内重新归一化。')
    scoped_program,scoped_rows,scoped_columns,scope_budget=acquisition_scope(cfg,a,program,rows,columns,budget)
    probe=noise_resource_probe(cfg,a,light,scoped_program)
    probe['scope_mode']=cfg.acquisition.scope_mode;probe['measured_columns']=len(scoped_columns)
    bins=histogram_bin_count(cfg,cfg.analysis_bin_ps)
    probe['histogram_work']=bins*len(scoped_columns)*cfg.spad.channels_h*cfg.spad.channels_v
    probe['histogram_blocked']=bins>a.max_histogram_bins or probe['histogram_work']>a.max_column_histogram_work
    probe['blocked']=probe['blocked'] or probe['histogram_blocked']
    selected=next((r for r in rows if r['measured'] and r['column_id']==column_id and r['emitted']),None)
    projection=ColumnPulseProjection(cfg,a,light,groups,info,rows)
    sample=None
    if selected:
        p=projection.evaluate(selected)
        sample={'cycle':selected['cycle'],'column_id':column_id,'pixel_photons':p['photons'].sum(axis=0).reshape(info['array_shape']).tolist(),
                'channel_photons':p['channel'].sum(axis=0).tolist(),'relative_h_mrad':p['relative_h'].tolist(),
                'relative_v_mrad':p['relative_v'].tolist(),'rx_axis_mrad':p['rx_axis'].tolist()}
    view.update(configuration=cfg.model_dump(),system_budget=system_budget_view(cfg.system_targets),
        optics=info,columns=columns,schedule=[r for r in rows if r['measured']],frame_budget=budget,
        motion=motion_view(cfg,a,rows,column_id),transport=transport_plan(cfg,columns),
        resource_probe=probe,selected_pulse_projection=sample,selected_column=column_id,
        ready_for_acquisition=not probe['blocked'],analysis_note='Parameter/plan preview only; no random records have been generated.')
    return stamp_result('C_column_plan_preview',cfg,a,view)


def ideal_histogram_reference(result,cfg,a,column_id,channels,edges):
    scan=result['column_scan'];rows=scan['warmup_schedule']+scan['schedule']
    observed=[r for r in rows if r['measured'] and r['column_id']==column_id]
    sources=[r for r in rows if r['emitted']]
    components=1 if cfg.scene_motion.range_gradient_m_per_rad==0 else a.spatial_angle_samples_h
    work=len(sources)*components*(len(edges)-1)*len(observed)
    if work>a.max_column_reference_work:
        return None,f'理想参考工作量{work}超过限额{a.max_column_reference_work}；可选择更粗的显示分箱。'
    weights=[];centers=[];response=float(effective_pde(Curve(cfg.spectral_inputs.pde)(cfg.tx.wavelength_nm),cfg.spad.fill_factor))
    if components==1:
        truth=scan['source_truth_by_cycle'];audit={r['cycle']:r for r in scan['pulse_optical_audit']}
        for row in sources:
            weights.append(np.asarray(truth[str(row['cycle'])]['photons'])[channels]*response)
            centers.append(row['emission_time_ns']+2*audit[row['cycle']]['range_min_m']/C*1e9+cfg.acquisition.calibration_delay_ns)
    else:
        info=result['optics'];groups=np.asarray(info['pixel_group_ids'])
        projection=ColumnPulseProjection(cfg,a,None,groups,info,rows)
        shape=np.asarray(info['tx_energy_fraction']).shape
        for row in sources:
            out=projection.evaluate(row)
            w=out['channel'].reshape(*shape,-1).sum(axis=0)[:,channels]*response
            weights.extend(w);centers.extend(out['arrival_ns'].reshape(shape)[0]+cfg.acquisition.calibration_delay_ns)
    counts=np.zeros((len(channels),len(edges)-1));weights=np.asarray(weights);centers=np.asarray(centers)
    tail=None if cfg.exposure.tail_fraction==0 else (cfg.exposure.tail_fraction,cfg.exposure.tail_tau_ns)
    if len(centers):
        for row in observed:
            for lo,hi in row['gate_segments_ns']:
                lower=np.maximum(row['start_ns']+edges[:-1],lo);upper=np.minimum(row['start_ns']+edges[1:],hi)
                valid=upper>lower
                mass=temporal_cdf(upper[None,valid]-centers[:,None],cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,tail)-temporal_cdf(lower[None,valid]-centers[:,None],cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,tail)
                counts[:,valid]+=weights.T@np.maximum(mass,0)
    times=(edges[:-1]+edges[1:])/2
    refs=[{'counts':row.tolist(),'high_resolution':{'time_ns':times.tolist(),'counts_per_nominal_bin':row.tolist()}} for row in counts]
    return refs,'理想信号为时间抖动、SPAD恢复与电子读出前的候选数；包括保存的源脉冲、预热和门并集，不是最终数字读出的期望。'


def selected_histogram(result,cfg,a,column_id,channels,bin_ps,include_reference):
    count=cfg.spad.channels_h*cfg.spad.channels_v
    if not channels or len(channels)!=len(set(channels)) or any(ch<0 or ch>=count for ch in channels):raise ValueError('Select distinct valid channels')
    if len(channels)>a.max_visible_channels:raise ValueError('Visible channel count exceeds configured limit')
    ratio=bin_ps/cfg.readout.tdc_bin_ps
    if not np.isfinite(ratio) or ratio<1 or not math.isclose(ratio,round(ratio),rel_tol=0,abs_tol=math.ulp(ratio)):
        raise ValueError('Display bin must be an integer multiple of the saved TDC bin')
    if column_id not in result['column_scan']['measured_column_ids']:raise ValueError('This column was not simulated in this task')
    stats=result['statistics']
    bins=histogram_bin_count(cfg,bin_ps)
    if bins>a.max_histogram_bins or len(channels)*bins*(stats['trial_count']+stats['noise_trial_count']+1)>a.max_column_selected_histogram_cells:
        raise ValueError('Selected histogram/statistics arrays exceed display limit')
    edges=histogram_edges(cfg,bin_ps)
    def hist(records):return histogram_for_records([r for r in records if r['column_id']==column_id],cfg,bin_ps,channels)
    h=hist(result['records']);trials=np.array([hist(r)['counts'] for r in stats['trial_records']]);noise=[hist(r)['counts'] for r in stats['noise_records']]
    summary={'trial_count':stats['trial_count'],'noise_trial_count':stats['noise_trial_count'],
        'lower':trials.min(axis=0).tolist() if len(trials)>1 else None,'upper':trials.max(axis=0).tolist() if len(trials)>1 else None,
        'noise_mean':np.mean(noise,axis=0).tolist() if noise else None,'method':stats['method']}
    refs,note=ideal_histogram_reference(result,cfg,a,column_id,channels,np.asarray(h['edges_ns'])) if include_reference else (None,'Not requested')
    est=SimpleNamespace(pulse_fwhm_ps=cfg.tx.pulse_fwhm_ps,pulse_shape=cfg.tx.pulse_shape,
        spad_jitter_fwhm_ps=cfg.spad.spad_jitter_fwhm_ps,other_jitter_fwhm_ps=cfg.readout.other_jitter_fwhm_ps,
        tdc_bin_ps=bin_ps,calibration_delay_ns=cfg.acquisition.calibration_delay_ns)
    ranges=[]
    for index,ch in enumerate(channels):
        estimates=[_estimate_range(est,np.array(h['time_ns']),sample[index],a)[0] for sample in trials if sample[index].sum()]
        estimates=[v for v in estimates if v is not None]
        ranges.append({'channel':ch,'valid_raw_estimates':len(estimates),
            'mean_raw_distance_m':float(np.mean(estimates)) if estimates else None,
            'sample_std_m':float(np.std(estimates,ddof=1)) if len(estimates)>1 else None,
            'note':'Conditional raw-estimate statistics, not calibrated detection probability.'})
    total=np.asarray(h['counts']).sum(axis=0)
    if total.sum():
        center=h['time_ns'][int(np.argmax(total))]
        half=max(a.ground_truth_extent_sigma*timing_sigma_ns(est),a.estimator_kernel_sigma*bin_ps*1e-3)
        focus=[max(h['edges_ns'][0],center-half),min(h['edges_ns'][-1],center+half)]
    else:focus=[h['edges_ns'][0],h['edges_ns'][-1]]
    return {'histogram':h,'statistics':summary,'references':refs,'reference_note':note,'range_statistics':ranges,
        'focus_window_ns':focus,'focus_note':'Display window around the strongest observed selected-channel bin; no truth ROI is used in ranging.',
        'column_id':column_id,'channels':channels,'recorded_total':sum(r['column_id']==column_id for r in result['records']),
        'configuration_sha256':result['provenance']['configuration_sha256']}

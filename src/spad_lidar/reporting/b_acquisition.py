"""Explicit B acquisition scopes, derived solely from saved configuration/records.

The folded ToF histogram already sums all measured exposures. A single-gate
observation must be selected by record.cycle, never by dividing that sum by N.
"""
from types import SimpleNamespace
from datetime import datetime,timezone
import numpy as np
from ..configuration import read_yaml
from ..processing.records import histogram_selected_records
from ..processing.statistics import histogram_sample_range
from .a_view import signal_ground_truth
from .noise_reference import candidate_noise_reference, rebin_noise_reference


def acquisition_context(cfg,a,optics,*,result=None):
    t=cfg.timing;n=t.laser_shots;preview=min(n,a.b_mechanism_preview_gates)
    saved_stats=(result or {}).get('statistics')
    trials=cfg.acquisition.monte_carlo_trials if result is None else saved_stats['trial_count'] if saved_stats else None
    initialization=(result or {}).get('audit',{}).get('initialization',{
        'mode':a.b_initial_condition,
        'warmup_cycles':0 if a.b_initial_condition=='fully_recovered' else a.readout_warmup_cycles})
    return {
        'shots':n,'period_ns':t.period_ns,'gate_start_ns':t.gate_start_ns,'gate_width_ns':t.gate_width_ns,
        'sequence_duration_ns':n*t.period_ns,'last_gate_close_ns':(n-1)*t.period_ns+t.gate_start_ns+t.gate_width_ns,
        'total_gate_open_ns':n*t.gate_width_ns,'gate_gap_ns':t.period_ns-t.gate_width_ns,
        'gate_preview':[{'index':i,'trigger_ns':i*t.period_ns,'open_ns':i*t.period_ns+t.gate_start_ns,
                         'close_ns':i*t.period_ns+t.gate_start_ns+t.gate_width_ns} for i in range(preview)],
        'gate_preview_end_ns':preview*t.period_ns,'gate_preview_count':preview,'gate_preview_truncated':preview<n,
        'initialization':initialization,'spad_dead_time_ns':cfg.device.spad_dead_time_ns,
        'tdc_dead_time_ns':cfg.readout.tdc_dead_time_ns,'readout_mode':cfg.readout.readout_mode,
        'trial_count':trials,'configured_trial_count':cfg.acquisition.monte_carlo_trials,
        'slot_scope':'This B observation accumulates its N-exposure sequence as one column. N*period is the simulated sequence length, not an independent hardware slot budget.',
        'independent_slot_budget_ns':None,'inter_slot_reset_ns':None,'inter_slot_reset_placement':'between_slots',
        'signal_sensor_photons_per_pulse':optics['budget']['signal_sensor_incident_photons_per_pulse'],
        'signal_sensor_photons_per_slot':n*optics['budget']['signal_sensor_incident_photons_per_pulse'],
        'scope_rules':[
            {'item':'光学能量/信号光子图','scope':'默认单发完整回波；可切换slot的N发光学期望总量。PDE/FF前，未按接收门裁切。'},
            {'item':'记录数、损失计数、测距','scope':'首次完整采集的 slot 累积；不叠加 Monte Carlo 重复。'},
            {'item':'探测直方图','scope':'默认 N 个 gate 按相对 Tx 时间折叠的 slot 累积；可选一个实际 gate。'},
            {'item':'PSF、光学份额、dB比值','scope':'归一化光学响应，无采集次数累加含义。'},
            {'item':'背景光子预算','scope':'按表内每门/每秒单位；不能与单发信号光子混用。'},
        ],
        'formulas':{key:read_yaml('formulas.yaml')[key] for key in ('b_gate_phase','b_slot_accumulation')},
        'formula_notes':{key:read_yaml('formula-notes.yaml')[key] for key in ('b_gate_phase','b_slot_accumulation')},
        'view_policy':{'preview_gate_limit':a.b_mechanism_preview_gates,'timeline_point_limit':a.b_timeline_max_points},
    }


def spatial_scope_values(illumination,shots):
    photons=np.asarray(illumination['signal_photons_per_pixel_per_pulse'])
    return {'per_pulse':{'signal_photons_per_pixel':photons.tolist(),'total_photons':float(photons.sum()),
                         'unit':'光子 / 像素 / 发','scope_label':'单发信号期望'},
            'slot':{'signal_photons_per_pixel':(photons*shots).tolist(),'total_photons':float(photons.sum()*shots),
                    'unit':'光子 / 像素 / slot','scope_label':f'本次 slot · {shots} 发信号期望'}}


def _rebin_factor(result,bin_ps):
    original=result['record_schema']['tdc_bin_ps'];factor=bin_ps/original
    if not np.isfinite(factor) or factor<1 or not np.isclose(factor,round(factor),rtol=0,atol=np.finfo(float).eps*max(1,factor)):
        raise ValueError('Display bin must be an integer multiple of acquisition resolution')
    return round(factor)


def exposure_counts(result,cfg,a,channels):
    """Exact aggregation of stored events, bounded by display points, not N*bins."""
    n=cfg.timing.laser_shots;points=min(n,a.b_timeline_max_points)
    boundaries=np.arange(points+1,dtype=np.int64)*n//points
    times=(boundaries[1:]-1)*cfg.timing.period_ns+cfg.timing.gate_start_ns+cfg.timing.gate_width_ns
    slot_end=cfg.timing.laser_shots*cfg.timing.period_ns
    mapping={ch:i for i,ch in enumerate(channels)};counts=np.zeros((len(channels),points),dtype=np.int64)
    for record in result['records']:
        row=mapping.get(record['channel'])
        if row is not None:
            cycle=record['cycle']
            if not 0<=cycle<n:raise ValueError('Saved record cycle lies outside measured B exposures')
            column=int(np.searchsorted(boundaries,cycle,side='right'))-1
            counts[row,column]+=1
    return {'channels':channels,'start_gate':boundaries[:-1].tolist(),'end_gate':(boundaries[1:]-1).tolist(),
            'gate_end_time_ns':times.tolist(),'sequence_duration_ns':slot_end,
            'counts':counts.tolist(),'cumulative_counts':counts.cumsum(axis=1).tolist(),
            'total_counts':counts.sum(axis=1).tolist(),'grouped':points<n,
            'note':'Blue bars are actual records per gate (or explicitly grouped gates); green curve is cumulative records from slot start. Derived from the first observation only.'}


def histogram_scope_view(result,cfg,a,scope,gate_index,bin_ps,channels):
    n=cfg.timing.laser_shots;channel_count=cfg.spad.channels_h*cfg.spad.channels_v
    if scope not in ('slot','gate'):raise ValueError('Unknown histogram scope')
    if not 0<=gate_index<n:raise ValueError('Gate index is outside this acquisition')
    if not channels or len(set(channels))!=len(channels) or len(channels)>a.max_visible_channels or any(ch<0 or ch>=channel_count for ch in channels):
        raise ValueError('Select unique valid channels within max_visible_channels')
    factor=_rebin_factor(result,bin_ps);selected=set(channels)
    records=[r for r in result['records'] if r['channel'] in selected and (scope=='slot' or r['cycle']==gate_index)]
    histogram=histogram_selected_records(records,cfg.timing.gate_start_ns,cfg.timing.gate_width_ns,bin_ps,channels)
    rows=[[] for _ in range(channel_count)]
    for ch,counts in zip(channels,histogram['counts']):rows[ch]=counts
    histogram['counts']=rows
    stats=result.get('statistics');statistics=None
    # Only folded repeated histograms were saved. Never derive single-gate
    # fluctuations by rescaling a slot's range or pretending fresh sampling.
    if scope=='slot' and stats:
        def rebin(values):
            if not values:return []
            array=np.asarray([[trial[ch] for ch in channels] for trial in values])
            return np.add.reduceat(array,np.arange(0,array.shape[-1],factor),axis=-1).tolist()
        trials=rebin(stats['trial_histograms']);noise=rebin(stats['noise_histograms']);bounds=histogram_sample_range(trials)
        def expand(rows):
            if rows is None:return None
            full=[[] for _ in range(channel_count)]
            for ch,row in zip(channels,rows):full[ch]=row
            return full
        statistics={'trial_count':stats['trial_count'],'noise_trial_count':stats['noise_trial_count'],
                    'lower':expand(bounds['lower_counts']),'upper':expand(bounds['upper_counts']),
                    'noise_mean':expand(np.mean(noise,axis=0).tolist()) if noise else None,
                    'method':stats['method'],'note':stats['note']}
    edges=np.asarray(histogram['edges_ns']);refs=[None for _ in range(channel_count)]
    shots_in_view=n if scope=='slot' else 1
    if result.get('references'):
        subdivisions=min(a.histogram_preview_subdivisions,a.max_histogram_preview_bins//(len(edges)-1))
        if len(channels)*((len(edges)-1)*subdivisions+a.ground_truth_plot_points)>a.max_lab_reference_cells:
            raise ValueError('Selected analytical reference arrays exceed max_lab_reference_cells')
        params={**cfg.optics.model_dump(exclude={'dataset'}),**cfg.device.model_dump(),**cfg.readout.model_dump(),
                **cfg.timing.model_dump(),'laser_shots':shots_in_view,'tdc_bin_ps':bin_ps}
        proxy=SimpleNamespace(**params);groups=np.asarray(result['optics']['pixel_group_ids'])
        photons=np.asarray(result['illumination']['signal_photons_per_pixel_per_pulse'])
        for ch in channels:
            budget=SimpleNamespace(signal_detected_per_pulse=result['references'][ch]['full_signal_total']/n,
                                   signal_sensor_incident_photons_per_pulse=float(photons[groups==ch].sum()))
            refs[ch]=signal_ground_truth(proxy,budget,edges,a)
    noise_reference=None
    if 'noise_reference' in result:
        if scope=='slot':noise_reference=rebin_noise_reference(result['noise_reference'],bin_ps)
        else:noise_reference=candidate_noise_reference(result['audit']['source'],result['optics']['pixel_group_ids'],1,cfg.timing.gate_width_ns,bin_ps)
    counts=[sum(row) if ch in selected else None for ch,row in enumerate(histogram['counts'])]
    return {'scope':scope,'gate_index':gate_index if scope=='gate' else None,'shots_in_view':shots_in_view,
            'view_generated_utc':datetime.now(timezone.utc).isoformat(),
            'channels':channels,'histogram':histogram,'references':refs if result.get('references') else None,
            'statistics':statistics,'noise_reference':noise_reference,'record_counts':counts,
            'timeline':exposure_counts(result,cfg,a,channels),
            'scope_label':f'slot 累积 · {n} 个 gate' if scope=='slot' else f'单 gate · G{gate_index} 的实际记录',
            'x_axis_label':'相对各次 Tx 的 ToF · ns' if scope=='slot' else f'相对 G{gate_index} Tx 的时间 · ns',
            'statistics_note':(f'{stats["trial_count"]} 次完整 slot 重复统计；误差棒不跨重复叠加计数。' if stats else '历史任务没有重复统计。') if scope=='slot' else '未保存逐 gate 重复统计，单 gate 不显示误差棒；没有重采样或用 slot 统计推造。',
            'reference_note':('单 gate 青线仅为本次 Tx 的单发解析参考，不包含其他曝光的迟到回波。' if scope=='gate' else f'青线为本次 {n} 发 slot 累积的纯信号解析参考。')
                +' 青线位于 PDE/FF 之后、SPAD 死时间与读出损失之前，不是预计的最终输出；虚线为连续密度乘标称分箱宽度，散点为分箱积分，两者峰值可不同。',
            'configuration_sha256':result['provenance']['configuration_sha256'],
            'processing_bin_ps':bin_ps,'view_policy':{'timeline_point_limit':a.b_timeline_max_points,'max_reference_cells':a.max_lab_reference_cells},
            'note':'Views of saved immutable records; no new acquisition. Counts use true record cycle, not N-normalized estimates.'}

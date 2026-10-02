"""Deterministic hardware budget. Reuses B optics; never predicts digital records."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import numpy as np
from pydantic import Field, model_validator
from . import __version__
from .configuration import read_yaml
from .curves import merge_config, Curve
from .models import SimulationConfig
from .spad.config import StrictConfig
from .experiments.system_config import BSystemConfig
from .experiments.spatial import project_illumination
from .scan.planning import SystemTargets, uniform_column_budget
from .numerics.temporal import temporal_pdf, pulse_interval_fractions
from .constants import C
from .reporting.spatial_flow import build_spatial_flow
from .budget_extensions import ElectricalBudgetConfig,RangeReferenceConfig,BudgetTransportSpec


class BudgetAssumptions(StrictConfig):
    reset_time_ns: float | None = Field(ge=0)
    wall_plug_efficiency: float | None = Field(gt=0, le=1)
    max_average_optical_power_w: float | None = Field(gt=0)
    max_peak_optical_power_w: float | None = Field(gt=0)
    prbs_enabled: bool
    prbs_chip_count: int | None = Field(ge=1, strict=True)
    prbs_chip_ns: float | None = Field(gt=0)
    prbs_on_count: int | None = Field(ge=1, strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.prbs_enabled:
            if any(v is None for v in (self.prbs_chip_count, self.prbs_chip_ns, self.prbs_on_count)):
                raise ValueError('PRBS预算需填写码片数、码片时长和开码片数')
            if self.prbs_on_count > self.prbs_chip_count:
                raise ValueError('PRBS开码片数不能超过总码片数')
        return self


class HardwareBudgetConfig(StrictConfig):
    system: BSystemConfig
    targets: SystemTargets
    assumptions: BudgetAssumptions
    transport: BudgetTransportSpec
    geometry: 'BudgetGeometry'
    rx_channel: 'BudgetRxChannel'
    electrical: ElectricalBudgetConfig
    range_reference: RangeReferenceConfig


class BudgetRxChannel(StrictConfig):
    h_width_mrad: float = Field(gt=0)
    v_width_deg: float | None = Field(gt=0,lt=180)


class BudgetGeometry(StrictConfig):
    vfov_deg: float = Field(gt=0,lt=180)
    tx_h_width_mrad: float = Field(gt=0)


HardwareBudgetConfig.model_rebuild()


def budget_channel_config(cfg,algorithms):
    """Validate the actual independent optical reference, using the common B core."""
    s=cfg.system;count=s.spad.channels_v;local=s.model_dump()
    dv=math.radians(cfg.geometry.vfov_deg)*1000/count
    rv=dv if cfg.rx_channel.v_width_deg is None else math.radians(cfg.rx_channel.v_width_deg)*1000
    if s.rx.rx_model=='dataset':raise ValueError('独立角通道预算需构造Rx，实测全阵列数据请在B页面使用')
    local['spad']['channels_v']=1
    local['tx'].update(pulse_average_power_w=s.tx.pulse_average_power_w/count,tx_center_h_mrad=0,tx_center_v_mrad=0,
        angle_h_min_mrad=-cfg.geometry.tx_h_width_mrad/2,angle_h_max_mrad=cfg.geometry.tx_h_width_mrad/2,
        angle_v_min_mrad=-dv/2,angle_v_max_mrad=dv/2)
    local['rx'].update(rx_angle_h_min_mrad=-cfg.rx_channel.h_width_mrad/2,rx_angle_h_max_mrad=cfg.rx_channel.h_width_mrad/2,
        rx_angle_v_min_mrad=-rv/2,rx_angle_v_max_mrad=rv/2)
    return SimulationConfig.for_experiment('system',local,algorithms.model_copy(update={
        'max_histogram_bins':algorithms.budget_max_histogram_bins,
        'max_lab_histogram_cells':algorithms.budget_max_histogram_bins}))


def resolve_budget(overrides, algorithms):
    sections = read_yaml('defaults.yaml')['experiments']
    from .experiments.configuration import experiment_defaults
    default_system=BSystemConfig.model_validate(experiment_defaults('system'))
    values = dict(system=merge_config(default_system.model_dump(),sections['budget_system']),
                  targets=SimulationConfig.system_targets({}).model_dump(),
                  assumptions=sections['budget'], transport=sections['budget_transport'],geometry=sections['budget_geometry'],rx_channel=sections['budget_rx_channel'],electrical=sections['budget_electrical'],range_reference=sections['budget_range_reference'])
    HardwareBudgetConfig.model_validate(values)  # Validate defaults before applying any overrides.
    from .legacy_config import migrate_pulse_energy
    overrides=dict(overrides)
    if 'system' in overrides:overrides['system']=migrate_pulse_energy(overrides['system'])
    cfg = HardwareBudgetConfig.model_validate(merge_config(values, overrides))
    ref=cfg.range_reference.model_dump();ref.update({k:ref[k] if ref[k] is not None else getattr(algorithms,'budget_reference_'+('points' if k=='points' else k)) for k in ('min_range_m','max_range_m','points')});cfg=HardwareBudgetConfig.model_validate({**cfg.model_dump(),'range_reference':ref})
    if cfg.range_reference.points>algorithms.budget_reference_max_points:raise ValueError('Range reference point limit exceeded')
    if max(len(cfg.range_reference.manual_points),len(cfg.range_reference.csv_points))>algorithms.budget_reference_max_measurements:raise ValueError('Measurement point limit exceeded')
    system=cfg.system.model_dump();tx=system['tx']
    vfov=cfg.geometry.vfov_deg
    vw=math.radians(vfov)*1000;hw=cfg.geometry.tx_h_width_mrad
    if cfg.system.spad.channels_h!=1:raise ValueError('系统预算为V向一维线阵，H读出通道数必须为1；H_binning仍可大于1')
    if tx['tx_model']!='uniform':raise ValueError('系统预算采用均匀空间光场，非均匀模型请在B页面研究')
    tx.update(angle_h_min_mrad=tx['tx_center_h_mrad']-hw/2,angle_h_max_mrad=tx['tx_center_h_mrad']+hw/2,
              angle_v_min_mrad=tx['tx_center_v_mrad']-vw/2,angle_v_max_mrad=tx['tx_center_v_mrad']+vw/2)
    dv=vw/cfg.system.spad.channels_v
    rv=dv if cfg.rx_channel.v_width_deg is None else math.radians(cfg.rx_channel.v_width_deg)*1000
    rx=system['rx'];rx.update(rx_angle_h_min_mrad=-cfg.rx_channel.h_width_mrad/2,rx_angle_h_max_mrad=cfg.rx_channel.h_width_mrad/2,
        rx_angle_v_min_mrad=tx['tx_center_v_mrad']-(vw-dv+rv)/2,rx_angle_v_max_mrad=tx['tx_center_v_mrad']+(vw-dv+rv)/2)
    if tx['tx_model']=='dataset':
        raise ValueError('系统预算的VFOV联动当前适用于构造Tx；数据库Tx请使用B页面按文件角域分析')
    cfg=HardwareBudgetConfig.model_validate({**cfg.model_dump(),'system':system,
        'geometry':{'vfov_deg':vfov,'tx_h_width_mrad':hw}})
    channels=cfg.system.spad.channels_h*cfg.system.spad.channels_v
    pixels=channels*cfg.system.spad.spads_per_channel
    if channels>algorithms.budget_max_channels:
        raise ValueError(f'系统预算角通道数量 {channels} 超过 budget_max_channels={algorithms.budget_max_channels} 软件资源保护限额')
    if pixels>algorithms.budget_max_physical_pixels:
        raise ValueError(f'系统预算物理像元总数 {pixels} 超过 budget_max_physical_pixels={algorithms.budget_max_physical_pixels} 软件资源保护限额')
    budget_channel_config(cfg,algorithms)
    if cfg.targets.slot_count > algorithms.max_column_count:
        raise ValueError('Column count exceeds max_column_count')
    return cfg


def calculate_budget(cfg, algorithms):
    from .reporting.display_numbers import display_number as fnum
    s, t, x = cfg.system, cfg.system.timing, cfg.assumptions
    time = uniform_column_budget(cfg.targets)
    # One uniform angular channel uses the shared B optical kernel. Identical
    # independent V channels are then accumulated without inventing a second model.
    count=s.spad.channels_v
    channel_cfg=budget_channel_config(cfg,algorithms)
    dv=channel_cfg.tx.angle_v_max_mrad-channel_cfg.tx.angle_v_min_mrad
    rv=channel_cfg.rx.rx_angle_v_max_mrad-channel_cfg.rx.rx_angle_v_min_mrad
    light, groups, optics = project_illumination(channel_cfg, algorithms, lambda *args: None, lambda: False)
    single_budget=dict(optics['budget'])
    fixed={'aperture_area_m2','angular_solid_angle_sr','tx_angular_coverage_fraction','reference_time_bin_ps'}
    optics['budget']={k:(v*count if isinstance(v,(float,int)) and k not in fixed else v) for k,v in single_budget.items()}
    b = optics['budget']
    n = t.laser_shots
    last = (n - 1) * t.period_ns
    gate_end = t.gate_start_ns + t.gate_width_ns
    # Minimum envelope through last gate and pulse FWHM; Gaussian tails remain unbounded.
    duration = last + max(gate_end, s.tx.pulse_fwhm_ps * 1e-3 / 2)
    slot = time['slot_max_ns']
    raw_margin = slot - duration
    reset = x.reset_time_ns
    margin = None if reset is None else raw_margin - reset
    usable = None if reset is None else slot - reset
    max_n = None if usable is None else max(0, math.floor((usable - max(gate_end, s.tx.pulse_fwhm_ps * 1e-3 / 2)) / t.period_ns) + 1)
    flight = 2 * s.scene.range_m / C * 1e9
    arrival = flight + s.acquisition.calibration_delay_ns
    gate_fraction = float(pulse_interval_fractions(arrival, t.gate_start_ns, gate_end, s.tx.pulse_shape, s.tx.pulse_fwhm_ps))
    omega = time['required_average_optical_rad_s']
    shots_second = n * cfg.targets.slot_count * cfg.targets.frame_rate_hz
    avg = b['tx_input_j'] * shots_second
    peak = float(s.tx.total_pulse_energy_nj * temporal_pdf(0., s.tx.pulse_shape, s.tx.pulse_fwhm_ps))
    channels = s.spad.channels_h * s.spad.channels_v
    pixels = channels * s.spad.spads_per_channel
    gate_open_ns = n * t.gate_width_ns
    background = (b['solar_candidate_rate_cps'] + b['other_candidate_rate_cps']) * gate_open_ns * 1e-9
    dark = pixels * (s.spad.dcr_cps_per_spad + s.spad.other_noise_cps_per_spad) * gate_open_ns * 1e-9
    signal = b['signal_candidate_avalanches_per_pulse'] * n * gate_fraction
    bins = math.ceil(t.gate_width_ns * 1000 / s.readout.tdc_bin_ps)
    from .electrical_budget import electrical_budget
    preview=sorted(set(np.linspace(0,cfg.targets.slot_count-1,min(cfg.targets.slot_count,algorithms.budget_frame_preview_slots),dtype=int).tolist()))
    electrical=electrical_budget(cfg,{**time,'frame_preview_indices':preview},duration,algorithms)
    selected=electrical['selected'];histogram=electrical['formats']['histogram']
    body_bytes=histogram.get('body_bytes_per_column');payload=histogram.get('total_bytes_per_column')
    mbps=selected.get('total_required_mbps');wire_ns=selected.get('wire_ns')
    per_channel = np.full(count,float(light.signal_photons_per_pulse.sum()))
    metrics = dict(column_time_us=slot/1000, acquisition_envelope_us=duration/1000,
        margin_without_reset_us=raw_margin/1000, time_margin_us=None if margin is None else margin/1000,
        max_pulses_per_column=max_n, angle_step_deg=time['angle_per_slot_deg'],
        required_optical_rad_s=omega, pulse_train_sweep_mrad=omega*last*1e-6,
        return_rotation_mrad=omega*flight*1e-6, flight_ns=flight, gate_fraction=gate_fraction,
        pulse_count=n, pulses_per_second=shots_second, column_energy_nj=s.tx.total_pulse_energy_nj*n,
        average_optical_power_w=avg, average_output_power_w=avg*s.tx.tx_efficiency,
        peak_optical_power_w=peak, electric_power_w=None if x.wall_plug_efficiency is None else avg/x.wall_plug_efficiency,
        emitter_heat_w=None if x.wall_plug_efficiency is None else avg*(1/x.wall_plug_efficiency-1),
        signal_candidates_per_column=signal, background_candidates_per_column=background,
        device_noise_candidates_per_column=dark, final_mixed_records=None,
        channels=channels, spads_per_channel=s.spad.spads_per_channel, physical_spads=pixels,
        histogram_bins=bins, histogram_body_bytes=body_bytes, histogram_payload_bytes=payload,
        average_payload_mbps=mbps, wire_time_us=None if wire_ns is None else wire_ns/1000,
        max_frame_rate_hz=None if reset is None else cfg.targets.scan_time_utilization*1e9/(cfg.targets.slot_count*(duration+reset)))
    checks=[]
    def check(key, label, status, detail):
        checks.append(dict(id=key, label=label, status=status, detail=detail))
    check('timing','列时间容量','fail' if raw_margin<0 or (margin is not None and margin<0) else 'unknown' if reset is None else 'pass',
          '复位耗时待提供；当前仅显示未计复位余量。' if reset is None else f'接收门/FWHM包络及复位后余量 {fnum(margin/1000)} μs；未包括无限高斯尾。')
    check('gate','目标回波中心','pass' if t.gate_start_ns<=arrival<gate_end else 'fail',f'回波中心 {fnum(arrival)} ns；门内单发光学能量份额 {fnum(gate_fraction)}，未含器件抖动。')
    check('motion','扫描期间空间变化','review',f'首末发射相隔 {fnum(metrics["pulse_train_sweep_mrad"])} mrad；飞行期间光学转角 {fnum(metrics["return_rotation_mrad"])} mrad。按匀速扫描估算，需C验证收发几何。')
    for key,label,value,limit in (('average','平均光功率',avg,x.max_average_optical_power_w),('peak','峰值光功率',peak,x.max_peak_optical_power_w)):
        check(key,label,'unknown' if limit is None else 'pass' if value<=limit else 'fail',
              'Tx光学前限额待提供。' if limit is None else f'需求 {fnum(value)} W / 限额 {fnum(limit)} W；余量 {fnum(limit-value)} W。')
    pipeline=selected.get('pipeline',{})
    link_flags=(selected.get('average_bandwidth_ok'),electrical.get('ports_ok'),pipeline.get('sustained_ok'))
    link_state='fail' if False in link_flags else 'unknown' if None in link_flags else 'pass'
    check('link','SPAD处理 / MIPI目标节拍',link_state,
          pipeline.get('note','载荷或时序规格未完整。')+('' if wire_ns is None else f' 最忙link单列发送 {fnum(wire_ns/1000)} μs / 目标slot {fnum(slot/1000)} μs；端口未知时不判整机满足。'))
    check('output_deadline','严格帧内发送截止','unknown' if selected.get('frame_ok') is None else 'pass' if selected['frame_ok'] else 'review',
          '固定流水延迟可以跨帧；严格帧截止与持续吞吐分开判断，积压及slot延后见电学板块。')
    check('readout','SPAD / TDC记录能力','unknown','候选雪崩不等于最终记录；此页未执行死时间、符合、容量竞争或计数器饱和仿真。')
    check('background','Rx背景角域','pass' if algorithms.background_angular_domain=='independent_rx' else 'review',
          '背景按独立Rx角域积分，固定Rx和环境时不随Tx角域变化；Rx外设为不接收，仍需用实测覆盖验证边界。' if algorithms.background_angular_domain=='independent_rx' else '历史算法快照：背景沿用Tx角域。')
    check('thermal','电热估算','unknown' if x.wall_plug_efficiency is None else 'review','电光效率待提供。' if x.wall_plug_efficiency is None else '仅估算发光器件电功率及非光损耗；不含驱动、电机、SPAD等功耗，也不推算结温。')
    prbs=None
    if x.prbs_enabled:
        code_ns=x.prbs_chip_count*x.prbs_chip_ns
        prbs=dict(period_ns=code_ns, on_fraction=x.prbs_on_count/x.prbs_chip_count,
            energy_nj=x.prbs_on_count*s.tx.total_pulse_energy_nj,
            code_average_power_w=x.prbs_on_count*s.tx.total_pulse_energy_nj/code_ns,
            nominal_periodic_range_m=C*code_ns*1e-9/2,
            sweep_mrad=omega*code_ns*1e-6, within_column=code_ns<=slot,
            pulse_fwhm_within_chip=s.tx.pulse_fwhm_ps*1e-3<x.prbs_chip_ns,
            note='独立候选方案：每个开码片发一个同能量短脉冲；一周期预算不计复位/最后回波。未生成码、不验证自相关/消歧/抗干扰；不替换上方等间隔多发结果。')
    rows=[dict(pulse=i+1, emission_ns=i*t.period_ns, gate_start_ns=i*t.period_ns+t.gate_start_ns,
               gate_end_ns=i*t.period_ns+gate_end, return_ns=i*t.period_ns+arrival)
          for i in range(min(n,algorithms.budget_timeline_max_pulses))]
    snapshot=dict(experiment=cfg.model_dump(), algorithms=algorithms.model_dump())
    definitions={name:read_yaml(name) for name in ('formulas.yaml','formula-notes.yaml','photon-flow.yaml')}
    formulas=definitions['formulas.yaml'];notes=definitions['formula-notes.yaml']
    limitations=[
        '确定性工程预算，无随机采样、Pd/PFA或测距精度结论；无眼安全认证结论。',
        '光子结果为B的静态均匀朗伯场景；等间隔多发按相同光学响应累计，不含扫描引起的截获变化。',
        '仅累计各发对应接收门内的本发信号；未计其他发脉冲尾部跨门贡献。高斯脉冲无有限完整包络。',
        '列间复位为预算参数，不代表C已实现复位；时间检查未含真实驱动建立/锁存延迟。',
        '背景按配置Rx接收域积分，域外设为不接收；数据库必须覆盖域内。自由运行门外背景对恢复状态的影响未在本预算求解。',
        'PRBS只作独立周期/能量/运动预算；芯片数据保留能力、码序列和解码闭环尚未验证。',
        '继承的默认光学为构造样例，不是当前实物系统实测值。']
    from .tx.angular import vertical_partition
    partition={'edges_mrad':np.linspace(s.tx.angle_v_min_mrad,s.tx.angle_v_max_mrad,count+1).tolist(),'fractions':[1/count]*count}
    pde_response=b['signal_candidate_avalanches_per_pulse']/b['signal_sensor_incident_photons_per_pulse'] if b['signal_sensor_incident_photons_per_pulse'] else 0.
    bg_pixel=(light.background_photons_per_second @ Curve(s.spectral_inputs.pde)(light.wavelength_nm))*s.spad.fill_factor
    bg_channel=np.full(count,float(np.asarray(bg_pixel).sum())*gate_open_ns*1e-9)
    per_hv=per_channel.reshape(s.spad.channels_v,s.spad.channels_h)
    by_v=[dict(v_index=i,angle_low_mrad=partition['edges_mrad'][i],angle_high_mrad=partition['edges_mrad'][i+1],
        tx_fraction=partition['fractions'][i],tx_energy_nj=s.tx.total_pulse_energy_nj*partition['fractions'][i],
        tx_pulse_average_power_w=s.tx.pulse_average_power_w*partition['fractions'][i],
        sensor_photons_per_pulse=per_hv[i].sum(),signal_candidates_per_column=per_hv[i].sum()*pde_response*n*gate_fraction,
        background_candidates_per_column=bg_channel.reshape(s.spad.channels_v,s.spad.channels_h)[i].sum()) for i in range(s.spad.channels_v)]
    metrics.update(pulse_average_power_w=s.tx.pulse_average_power_w,single_pulse_energy_nj=s.tx.total_pulse_energy_nj,
                   horizontal_angle_step_mrad=math.radians(metrics['angle_step_deg'])*1000,vfov_deg=cfg.geometry.vfov_deg,vertical_angle_step_deg=cfg.geometry.vfov_deg/s.spad.channels_v,
                   channel_power_w=s.tx.pulse_average_power_w/count,channel_energy_nj=s.tx.total_pulse_energy_nj/count,
                   tx_channel_v_deg=cfg.geometry.vfov_deg/count,tx_channel_v_mrad=dv,rx_channel_v_deg=math.degrees(rv*1e-3),rx_channel_v_mrad=rv,tx_channel_h_deg=math.degrees(cfg.geometry.tx_h_width_mrad*1e-3),rx_channel_h_deg=math.degrees(cfg.rx_channel.h_width_mrad*1e-3),rx_channel_h_mrad=cfg.rx_channel.h_width_mrad)
    result=dict(metrics=metrics, constraints=checks,vertical_budget={'rows':by_v,
        'note':'均匀独立角通道预算：全线阵功率按V线数均分；每通道复用相同B光学核，未建模跨通道PSF串扰。',
        'tx_h_full_mrad':cfg.geometry.tx_h_width_mrad,'tx_v_full_mrad':math.radians(cfg.geometry.vfov_deg)*1000,
        'rx_h_bounds_mrad':[s.rx.rx_angle_h_min_mrad,s.rx.rx_angle_h_max_mrad],
        'rx_v_bounds_mrad':[s.rx.rx_angle_v_min_mrad,s.rx.rx_angle_v_max_mrad]},timing={**time,'rows':rows,'truncated':n>len(rows),
        'envelope_ns':duration,'reset_ns':reset,'plot_end_ns':max(slot,duration+(0 if reset is None else reset),last+arrival)},
        photon_flow=build_spatial_flow(single_budget,None), optical_budget=b,
        channel_sensor_photons_per_pulse=per_channel.tolist(), prbs=prbs,
        configuration=snapshot, definitions=definitions,
        formulas=[dict(id=k,latex=formulas[k],note=notes[k]) for k in ('pulse_equivalent_power','hardware_budget_channel','c_high_level_frame','c_high_level_slot','c_high_level_angle','hardware_budget_time','hardware_budget_power','hardware_budget_histogram','hardware_budget_prbs','budget_hist_copy_rate','budget_mipi_payload','budget_mipi_capacity','budget_range_fisher')],
        limitations=limitations,
        provenance=dict(utc=datetime.now(timezone.utc).isoformat(),model_version=__version__,
            configuration_sha256=sha256(json.dumps(snapshot,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            optical_dataset_sha256=optics['dataset_sha256'], definitions_sha256=sha256(json.dumps(definitions,sort_keys=True).encode()).hexdigest(),
            sampling='deterministic-no-random-sampling',source='YAML defaults + validated overrides; B optical core + uniform column planning'))
    from .reporting.budget_schematic import budget_schematic
    result['single_channel']={'configuration':channel_cfg.model_dump(),'optical_budget':single_budget,'tx_v_width_deg':cfg.geometry.vfov_deg/count,
        'rx_v_width_deg':math.degrees(rv*1e-3),'centers_v_mrad':((np.asarray(partition['edges_mrad'][:-1])+np.asarray(partition['edges_mrad'][1:]))/2).tolist()}
    result['limitations'].append('本页为均匀独立角通道预算；B全阵列仿真另计实际成像与跨通道分配，不保证两者总记录一致。')
    from .reporting.budget_windows import channel_windows
    result['channel_photons']=channel_windows(channel_cfg,single_budget,arrival,algorithms)
    result['timing']['frame_preview_indices']=sorted(set(np.linspace(0,cfg.targets.slot_count-1,min(cfg.targets.slot_count,algorithms.budget_frame_preview_slots),dtype=int).tolist()))
    result['timing']['frame_preview_slots']=[{'index':i,'start_ns':time['scan_allocatable_ns']*(i/cfg.targets.slot_count),'end_ns':time['scan_allocatable_ns']*((i+1)/cfg.targets.slot_count)} for i in result['timing']['frame_preview_indices']]
    result['schematic']=budget_schematic(cfg,optics,algorithms,result['single_channel'])
    from .electrical_budget import electrical_budget
    try:
        SimulationConfig.for_experiment('system',cfg.system.model_dump(),algorithms)
        result['b_simulation_runnable']=True;result['b_simulation_blocker']=None
    except ValueError as exc:
        result['b_simulation_runnable']=False
        result['b_simulation_blocker']='完整B事件仿真暂不可运行：'+str(exc)
        result['limitations'].append('系统预算仅计算代表通道静态光学并汇总，未运行整阵列事件仿真。'+result['b_simulation_blocker'])
    result['electrical']=electrical
    from .range_reference import range_reference
    result['range_reference']=range_reference(cfg,single_budget,algorithms) if cfg.range_reference.enabled else None
    json.dumps(result,allow_nan=False)  # Reject overflow, never serialize NaN/Infinity.
    return result

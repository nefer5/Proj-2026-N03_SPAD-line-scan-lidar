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
from .scan.column_config import TransportSpec
from .numerics.temporal import temporal_pdf, pulse_interval_fractions
from .constants import C
from .reporting.spatial_flow import build_spatial_flow


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
    transport: TransportSpec
    geometry: 'BudgetGeometry'


class BudgetGeometry(StrictConfig):
    vfov_deg: float | None = Field(gt=0,lt=180)
    tx_h_width_mrad: float = Field(gt=0)


HardwareBudgetConfig.model_rebuild()


def resolve_budget(overrides, algorithms):
    sections = read_yaml('defaults.yaml')['experiments']
    values = dict(system=SimulationConfig.for_experiment('system', {}, algorithms).model_dump(),
                  targets=SimulationConfig.system_targets({}).model_dump(),
                  assumptions=sections['budget'], transport=sections['columns']['transport'],geometry=sections['budget_geometry'])
    HardwareBudgetConfig.model_validate(values)  # Validate defaults before applying any overrides.
    from .legacy_config import migrate_pulse_energy
    overrides=dict(overrides)
    if 'system' in overrides:overrides['system']=migrate_pulse_energy(overrides['system'])
    cfg = HardwareBudgetConfig.model_validate(merge_config(values, overrides))
    system=cfg.system.model_dump();tx=system['tx']
    vfov=cfg.geometry.vfov_deg
    if vfov is None:vfov=math.degrees((tx['angle_v_max_mrad']-tx['angle_v_min_mrad'])*1e-3)
    vw=math.radians(vfov)*1000;hw=cfg.geometry.tx_h_width_mrad
    tx.update(angle_h_min_mrad=tx['tx_center_h_mrad']-hw/2,angle_h_max_mrad=tx['tx_center_h_mrad']+hw/2,
              angle_v_min_mrad=tx['tx_center_v_mrad']-vw/2,angle_v_max_mrad=tx['tx_center_v_mrad']+vw/2)
    if tx['tx_model']=='dataset':
        raise ValueError('系统预算的VFOV联动当前适用于构造Tx；数据库Tx请使用B页面按文件角域分析')
    cfg=HardwareBudgetConfig.model_validate({**cfg.model_dump(),'system':system,
        'geometry':{'vfov_deg':vfov,'tx_h_width_mrad':hw}})
    SimulationConfig.for_experiment('system', cfg.system.model_dump(), algorithms)
    if cfg.targets.slot_count > algorithms.max_column_count:
        raise ValueError('Column count exceeds max_column_count')
    return cfg


def calculate_budget(cfg, algorithms):
    s, t, x = cfg.system, cfg.system.timing, cfg.assumptions
    time = uniform_column_budget(cfg.targets)
    light, groups, optics = project_illumination(s, algorithms, lambda *args: None, lambda: False)
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
    bits = cfg.transport.histogram_count_bits
    body_bytes = None if bits is None else math.ceil(bins * channels * bits / 8)
    header = cfg.transport.column_header_bytes
    payload = None if body_bytes is None or header is None else body_bytes + header
    mbps = None if payload is None else payload * 8 * cfg.targets.slot_count * cfg.targets.frame_rate_hz / 1e6
    wire_ns = None if payload is None or cfg.transport.mipi_net_mbps is None else payload * 8 / cfg.transport.mipi_net_mbps * 1000
    per_channel = np.bincount(groups, weights=light.signal_photons_per_pulse.sum(axis=1), minlength=channels)
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
          '复位耗时待提供；当前仅显示未计复位余量。' if reset is None else f'接收门/FWHM包络及复位后余量 {margin/1000:.6g} μs；未包括无限高斯尾。')
    check('gate','目标回波中心','pass' if t.gate_start_ns<=arrival<gate_end else 'fail',f'回波中心 {arrival:.6g} ns；门内单发光学能量份额 {gate_fraction:.6g}，未含器件抖动。')
    check('motion','扫描期间空间变化','review',f'首末发射相隔 {metrics["pulse_train_sweep_mrad"]:.6g} mrad；飞行期间光学转角 {metrics["return_rotation_mrad"]:.6g} mrad。按匀速扫描估算，需C验证收发几何。')
    for key,label,value,limit in (('average','平均光功率',avg,x.max_average_optical_power_w),('peak','峰值光功率',peak,x.max_peak_optical_power_w)):
        check(key,label,'unknown' if limit is None else 'pass' if value<=limit else 'fail',
              'Tx光学前限额待提供。' if limit is None else f'需求 {value:.6g} W / 限额 {limit:.6g} W；余量 {limit-value:.6g} W。')
    check('link','原始直方图输出','unknown' if wire_ns is None else 'pass' if wire_ns<=slot else 'fail',
          '计数位宽、列头字节及净载荷速率齐备后计算；当前不评估DSP或缓冲调度。' if wire_ns is None else f'单列传输 {wire_ns/1000:.6g} μs / 列周期 {slot/1000:.6g} μs；无积压持续输出条件，仍需验证缓冲。')
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
    partition=vertical_partition(optics['tx_v_edges_mrad'],np.asarray(optics['tx_energy_fraction']).sum(axis=1),s.spad.channels_v)
    pde_response=b['signal_candidate_avalanches_per_pulse']/b['signal_sensor_incident_photons_per_pulse'] if b['signal_sensor_incident_photons_per_pulse'] else 0.
    bg_pixel=(light.background_photons_per_second @ Curve(s.spectral_inputs.pde)(light.wavelength_nm))*s.spad.fill_factor
    bg_channel=np.bincount(groups,weights=np.asarray(bg_pixel),minlength=channels)*gate_open_ns*1e-9
    per_hv=per_channel.reshape(s.spad.channels_v,s.spad.channels_h)
    by_v=[dict(v_index=i,angle_low_mrad=partition['edges_mrad'][i],angle_high_mrad=partition['edges_mrad'][i+1],
        tx_fraction=partition['fractions'][i],tx_energy_nj=s.tx.total_pulse_energy_nj*partition['fractions'][i],
        tx_pulse_average_power_w=s.tx.pulse_average_power_w*partition['fractions'][i],
        sensor_photons_per_pulse=per_hv[i].sum(),signal_candidates_per_column=per_hv[i].sum()*pde_response*n*gate_fraction,
        background_candidates_per_column=bg_channel.reshape(s.spad.channels_v,s.spad.channels_h)[i].sum()) for i in range(s.spad.channels_v)]
    metrics.update(pulse_average_power_w=s.tx.pulse_average_power_w,single_pulse_energy_nj=s.tx.total_pulse_energy_nj,
                   vfov_deg=cfg.geometry.vfov_deg,vertical_angle_step_deg=cfg.geometry.vfov_deg/s.spad.channels_v)
    result=dict(metrics=metrics, constraints=checks,vertical_budget={'rows':by_v,
        'note':'Tx列按VFOV等角分区，按当前Tx角格内常密度积分；Rx列按实际V像素组汇总所有H路。两种索引不保证一一对应（成像可倒置、失配或溢出）。',
        'tx_h_full_mrad':cfg.geometry.tx_h_width_mrad,'tx_v_full_mrad':math.radians(cfg.geometry.vfov_deg)*1000,
        'rx_h_bounds_mrad':[s.rx.rx_angle_h_min_mrad,s.rx.rx_angle_h_max_mrad],
        'rx_v_bounds_mrad':[s.rx.rx_angle_v_min_mrad,s.rx.rx_angle_v_max_mrad]},timing={**time,'rows':rows,'truncated':n>len(rows),
        'envelope_ns':duration,'reset_ns':reset,'plot_end_ns':max(slot,duration+(0 if reset is None else reset),last+arrival)},
        photon_flow=build_spatial_flow(b,None), optical_budget=b,
        channel_sensor_photons_per_pulse=per_channel.tolist(), prbs=prbs,
        configuration=snapshot, definitions=definitions,
        formulas=[dict(id=k,latex=formulas[k],note=notes[k]) for k in ('pulse_equivalent_power','c_high_level_frame','c_high_level_slot','c_high_level_angle','hardware_budget_time','hardware_budget_power','hardware_budget_histogram','hardware_budget_prbs')],
        limitations=limitations,
        provenance=dict(utc=datetime.now(timezone.utc).isoformat(),model_version=__version__,
            configuration_sha256=sha256(json.dumps(snapshot,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            optical_dataset_sha256=optics['dataset_sha256'], definitions_sha256=sha256(json.dumps(definitions,sort_keys=True).encode()).hexdigest(),
            sampling='deterministic-no-random-sampling',source='YAML defaults + validated overrides; B optical core + uniform column planning'))
    json.dumps(result,allow_nan=False)  # Reject overflow, never serialize NaN/Infinity.
    return result

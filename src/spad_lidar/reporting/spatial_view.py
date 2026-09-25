"""Common optical parameter figures, spatial responses and explicit dB conventions."""
from types import SimpleNamespace
import numpy as np
from ..configuration import read_yaml
from ..constants import C
from ..curves import Curve
from ..filters import FilterResponse
from ..spectra import spectral_components
from ..spad.device import effective_pde
from ..rx.spatial import image_center
from ..adapters.optical_data import RxTable, RxData
from .a_view import laser_quantities, filter_profile
from ..numerics.temporal import timing_sigma_ns

def channel_db_tables(fractions):
    """Conditional channel energy ratios, NOT a set of independent input excitations.

    Rows are observed channels; columns are reference channels. None means the
    reference has zero power; '-inf' means zero numerator and positive reference.
    No epsilon replacement and no clipping are applied to numerical exports.
    """
    matrices = []
    for row in np.asarray(fractions):
        matrix = []
        for numerator in row:
            matrix.append([None if denominator == 0 else '-inf' if numerator == 0
                           else float(10*(np.log10(numerator)-np.log10(denominator)))
                           for denominator in row])
        matrices.append(matrix)
    return {'matrix_db': matrices,
            'strongest_channel': np.argmax(fractions, axis=1).tolist(),
            'definition': '10 log10(eta_observed / eta_reference)',
            'quantity': 'PSF energy/power fraction at the same wavelength, before PDE/FF',
            'orientation': 'rows=observed channel, columns=reference channel, fixed incident angular cell',
            'zero_numerator': '-inf', 'zero_reference': None,
            'note': '20 log10 applies to amplitude ratios only when power is proportional to amplitude squared. This is not that amplitude definition.'}


def parameter_figures(base, cfg, interface, optics, psfs, algorithms):
    """Use shared A plotting sources, plus frozen B data; no JS physical formulas."""
    derived = laser_quantities(base, algorithms)
    derived['filter']=filter_profile(base,algorithms)
    derived['spectra']=spectral_components(base,algorithms,plot=True)
    derived['tof_ns']=2*cfg.optics.range_m/C*1e9+cfg.optics.calibration_delay_ns
    curves = derived['spectra']['curves']
    wavelength = np.asarray(curves['wavelength_nm'])
    response = effective_pde(np.asarray(curves['pde']), cfg.device.fill_factor)
    transmission = FilterResponse(base).evaluate(wavelength)
    def series(label, x, y, color, **extra):
        return {'label': label, 'x': list(x), 'y': list(y), 'color': color, **extra}
    def figure(title, x_label, y_label, items, note, **extra):
        return dict(title=title, x_label=x_label, y_label=y_label, series=items, note=note, **extra)
    pulse = figure('Tx 时间脉冲 · 光学前', '相对发射时刻 / ps', '功率 / W',
        [series('Tx 光学前功率', derived['pulse']['time_ps'], derived['pulse']['power_w'], 'cyan')],
        ('曲线积分为配置 Tx 角域内、Tx 光学前的单脉冲能量；角域内份额归一化。'
         if 'tx_energy_normalization' in optics else '曲线保留历史工况的Tx前全光斑单发能量与当时的角域截断定义。')
        +' 峰值与平均功率由 Python 公共核心计算。',
        facts=[['峰值功率', derived['peak_power_w'], 'W'], ['平均功率', derived['average_power_w'], 'W'],
               ['单脉冲能量', cfg.optics.total_pulse_energy_nj, 'nJ'], ['时间 FWHM', cfg.optics.pulse_fwhm_ps, 'ps']])
    filt = derived['filter']
    filter_fig = figure('滤光片透过率', '波长 / nm', '透过率',
        [series('透过率', filt['wavelength_nm'], filt['transmission'], 'cyan',
                points_x=filt['original_wavelength_nm'], points_y=filt['original_transmission'])],
        filt['note'], marker_x=base.wavelength_nm,
        facts=[['激光处透过率', filt['laser_transmission'], ''], ['加权带宽', filt['weighted_bandwidth_nm'], 'nm']])
    solar = figure('太阳光谱 · 目标面辐照度', '波长 / nm', 'W / (m² · nm)',
        [series('太阳辐照度', wavelength.tolist(), curves['solar_irradiance'], 'amber',
                points_x=curves['solar_original_x'], points_y=curves['solar_original_y'])],
        '按目标面照度归一化；标准谱为项目现有 AM1.5G 数据。此图和背景辐亮度图的单位不同。',
        marker_x=base.wavelength_nm, facts=[['照度', derived['spectra']['solar_lux'], 'lux'],
          ['谱积分辐照度', derived['spectra']['solar_irradiance_w_m2'], 'W / m²']])
    environment = figure('接收方向背景光谱', '波长 / nm', 'W / (m² · sr · nm)',
        [series('太阳反射', wavelength.tolist(), curves['solar_radiance'], 'amber'),
         series('其他环境光', wavelength.tolist(), curves['other_radiance'], 'blue',
                points_x=curves['other_original_x'], points_y=curves['other_original_y']),
         series('合计', wavelength.tolist(), curves['total_radiance'], 'cyan')],
        '太阳经目标反射后，与接收方向的其他环境光以同一辐亮度单位相加。', marker_x=base.wavelength_nm)
    pde = figure('SPAD PDE 与有效响应', '波长 / nm', '概率 / 无量纲',
        [series('PDE 输入', wavelength.tolist(), curves['pde'], 'blue',
                points_x=curves['pde_original_x'], points_y=curves['pde_original_y']),
         series('PDE × FF', wavelength.tolist(), response.tolist(), 'cyan')],
        'PDE 和乘 FF 后的有效响应分开显示；不包含死时间或电子读出损失。', marker_x=base.wavelength_nm)
    combined = figure('滤光片 × PDE × FF', '波长 / nm', '光谱响应 / 无量纲',
        [series('T × PDE × FF', wavelength.tolist(), (transmission*response).tolist(), 'cyan')],
        '仅含滤光片与探测响应；未包含入瞳面积、Rx 收光效率、PSF 截获率或读出损失。', marker_x=base.wavelength_nm)
    tx = np.asarray(optics['tx_energy_fraction'])
    he, ve = np.asarray(optics['tx_h_edges_mrad']), np.asarray(optics['tx_v_edges_mrad'])
    tx_profile = figure('Tx 角分布 · H/V 边缘份额', '光学角 / mrad', '角单元能量份额',
        [series('H 剖面（沿 V 求和）', ((he[:-1]+he[1:])/2).tolist(), tx.sum(axis=0).tolist(), 'cyan'),
         series('V 剖面（沿 H 求和）', ((ve[:-1]+ve[1:])/2).tolist(), tx.sum(axis=1).tolist(), 'amber')],
        ('角域内能量份额总和为 1；输入单发能量属于此角域，不额外扣除角域外高斯尾部。'
         if 'tx_energy_normalization' in optics else '历史采集：保留当时的角域份额与截断口径；重新运行后使用域内归一化。')
        +' H/V 曲线沿另一轴求和，显示积分份额，不是每 mrad 密度。', heatmap='tx',
        facts=[['角域份额合计', float(tx.sum()), ''],
               ['域内单发能量 · Tx前' if 'tx_energy_normalization' in optics else '历史全光斑能量 · Tx前', cfg.optics.total_pulse_energy_nj, 'nJ']])
    oh, ov = np.asarray(optics['angular_h_centers_mrad']), np.asarray(optics['angular_v_centers_mrad'])
    hu, vu = np.unique(oh), np.unique(ov)
    mapping = figure('Rx 几何映射 · 成像倒置', '入射光学角 / mrad', '像面中心 / μm',
        [series('H → x（f_H）', hu.tolist(), image_center(cfg.optics,hu,np.zeros_like(hu))[0].tolist(), 'cyan'),
         series('V → y（f_V）', vu.tolist(), image_center(cfg.optics,np.zeros_like(vu),vu)[1].tolist(), 'amber')],
        '两轴分别使用 f_H / f_V；正入射角映射到负像面位置，偏移量在成像后相加。',
        facts=[['f_H', interface['optics']['focal_length_h_mm'], 'mm'], ['f_V', interface['optics']['focal_length_v_mm'], 'mm']])
    ix = int(np.argmin(oh**2+ov**2))
    psf = np.asarray(psfs[ix]); xe=np.asarray(optics['dataset']['rx']['x_edges_um']);ye=np.asarray(optics['dataset']['rx']['y_edges_um'])
    from .psf_view import psf_parameter_figure
    psf_fig=psf_parameter_figure(cfg.optics,algorithms,psf,xe,ye)
    if cfg.optics.rx_model not in ('gaussian_psf','super_gaussian_psf'):
        all_psfs=np.asarray(psfs);capture=all_psfs.sum(axis=(1,2))
        xc=np.divide(all_psfs.sum(axis=1)@((xe[:-1]+xe[1:])/2),capture,out=np.full_like(capture,np.nan),where=capture>0)
        yc=np.divide(all_psfs.sum(axis=2)@((ye[:-1]+ye[1:])/2),capture,out=np.full_like(capture,np.nan),where=capture>0)
        hsel=(ov==vu[np.argmin(np.abs(vu))])&np.isfinite(xc)
        vsel=(oh==hu[np.argmin(np.abs(hu))])&np.isfinite(yc)
        mapping=figure('Rx 响应的像面质心','入射光学角 / mrad','截获光质心 / μm',
            [series('H → x 质心',oh[hsel].tolist(),xc[hsel].tolist(),'cyan'),
             series('V → y 质心',ov[vsel].tolist(),yc[vsel].tolist(),'amber')],
            '由当前响应矩阵在有限阵列上的像素积分计算；边缘截断会影响质心。数据库/均匀模型不使用构造焦距公式；无截获响应的点不补造。')
    extent=algorithms.ground_truth_extent_sigma*timing_sigma_ns(base)
    focus=[max(cfg.timing.gate_start_ns,derived['tof_ns']-extent),
           min(cfg.timing.gate_start_ns+cfg.timing.gate_width_ns,derived['tof_ns']+extent)]
    if focus[0]>=focus[1]:focus=[cfg.timing.gate_start_ns,cfg.timing.gate_start_ns+cfg.timing.gate_width_ns]
    if cfg.optics.rx_model in ('gaussian_psf','super_gaussian_psf') and cfg.optics.mapping_mode=='legacy_upright':
        mapping['title']='Rx 几何映射 · 历史正向约定'
        mapping['note']='此工况显式保留旧版正向映射；切换为倒置后，必须重新采集。'
    return {'pulse':pulse,'filter':filter_fig,'solar':solar,'environment':environment,'pde':pde,
        'combined':combined,'tx_profile':tx_profile,'mapping':mapping,'psf':psf_fig,
        'timing':{'title':'采集时序与接收门','period_ns':cfg.timing.period_ns,
          'gate_start_ns':cfg.timing.gate_start_ns,'gate_end_ns':cfg.timing.gate_start_ns+cfg.timing.gate_width_ns,
          'echo_ns':derived['tof_ns'],'pulse_fwhm_ns':cfg.optics.pulse_fwhm_ps*1e-3,
          'shots':cfg.timing.laser_shots,'prf_hz':base.laser_prf_hz,'acquisition_time_ms':derived['acquisition_time_ms'],
          'focus_window_ns':focus,
          'note':'发射标记仅定位触发时刻；实际脉宽见 Tx 波形。接收门只表示采集窗口。'}}


def optical_view(cfg, algorithms, optics, laser_shots=None):
    from ..experiments.system_config import form_values
    from .readout_layout import readout_layout
    interface=form_values(cfg)
    rx=RxData.model_validate(optics['dataset']['rx'])
    _,psfs=RxTable(rx).evaluate(cfg.optics.wavelength_nm,optics['angular_h_centers_mrad'],optics['angular_v_centers_mrad'])
    if len(optics['angle_to_channel_fraction'])*len(optics['angle_to_channel_fraction'][0])**2>algorithms.max_channel_ratio_cells:
        raise ValueError('Channel ratio matrices exceed max_channel_ratio_cells')
    parameters={**cfg.optics.model_dump(exclude={'dataset'}),'dataset':cfg.optics.dataset,**cfg.device.model_dump(),**cfg.readout.model_dump(),
                **cfg.timing.model_dump(),'spectral_inputs':cfg.spectral_inputs,
                'pulse_energy_nj':cfg.optics.total_pulse_energy_nj,'laser_prf_hz':1e9/cfg.timing.period_ns}
    shots=getattr(cfg.timing,'laser_shots',laser_shots)
    if shots is None:raise ValueError('Scan parameter view requires an explicit emitted-pulse count')
    parameters['laser_shots']=shots
    proxy=SimpleNamespace(**parameters)
    plot_cfg=SimpleNamespace(optics=cfg.optics,device=cfg.device,readout=cfg.readout,
                             timing=SimpleNamespace(**{**cfg.timing.model_dump(),'laser_shots':shots}))
    return {'form_configuration':interface,'readout_layout':readout_layout(optics),'x_edges_um':rx.x_edges_um,'y_edges_um':rx.y_edges_um,
            'angle_psfs':psfs.tolist(),'crosstalk':channel_db_tables(optics['angle_to_channel_fraction']),
            'parameter_figures':parameter_figures(proxy,plot_cfg,interface,optics,psfs,algorithms),
            'formulas':{key:read_yaml('formulas.yaml')[key] for key in ('b_rx_mapping_inverted','b_rx_mapping_legacy','b_channel_ratio_db','b_response_matrix','b_readout_channel_index')},
            'formula_notes':{key:read_yaml('formula-notes.yaml')[key] for key in ('b_rx_mapping_inverted','b_rx_mapping_legacy','b_channel_ratio_db','b_response_matrix','b_readout_channel_index')}}

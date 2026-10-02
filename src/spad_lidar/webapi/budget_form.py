"""Semantic form layout only; defaults, units and validation remain canonical."""


def field(path,label=None,full=False,when=None,labels_by_shape=None):
    value={'path':path}
    if label:value['label']=label
    if full:value['full']=True
    if when:value['when']=when
    if labels_by_shape:value['labels_by_shape']=labels_by_shape
    return value


def section(title,fields,unit=None,derived=None,when=None):
    value={'title':title,'fields':[field(p) if isinstance(p,str) else p for p in fields]}
    if unit:value['unit']=unit
    if derived:value['derived']=derived
    if when:value['when']=when
    return value


def condition(path,*values):return {'path':path,'values':list(values)}


FORM_LAYOUT=[
 {'module':'系统目标','sections':[
  section('系统视场',[field('targets.hfov_deg','H · 水平'),field('geometry.vfov_deg','V · 垂直')],'deg'),
  section('点云数量',[field('targets.slot_count','列数 / slot'),field('system.spad.channels_v','线数 / V通道')],derived=['channelVReadout','angularSampling']),
  section('扫描时序',['targets.frame_rate_hz','targets.scan_time_utilization'])]},
 {'module':'Tx发射','sections':[
  section('光源',['system.tx.pulse_average_power_w','system.tx.wavelength_nm']),
  section('时间脉冲',['system.tx.pulse_shape','system.tx.pulse_fwhm_ps']),
  section('Tx光学效率',['system.tx.tx_efficiency']),
  section('单通道发光角域',[field('geometry.tx_h_width_mrad','H · 水平')],'mrad',['txVReadout','channelDerived']),
  section('列内多发',['system.acquisition.laser_shots','system.acquisition.period_ns'])]},
 {'module':'场景','sections':[
  section('目标',['system.scene.range_m','system.scene.target_reflectivity']),
  section('传播与重叠',['system.scene.atmospheric_one_way_transmission','system.scene.overlap_factor'])]},
 {'module':'Rx接收','sections':[
  section('单通道收光角域',[field('rx_channel.h_width_mrad','H · 水平'),field('rx_channel.v_width_deg','V · 垂直')],'mrad',['rxDerived','followRxV']),
  section('入瞳几何',[
   field('system.rx.rx_aperture_shape','形状',True),
   field('system.rx.rx_aperture_mm','直径 D',True,condition('system.rx.rx_aperture_shape','circle')),
   field('system.rx.rx_aperture_width_mm','H · 全宽',when=condition('system.rx.rx_aperture_shape','ellipse','rectangle'),labels_by_shape={'ellipse':'H · 全轴','rectangle':'H · 全宽'}),
   field('system.rx.rx_aperture_height_mm','V · 全高',when=condition('system.rx.rx_aperture_shape','ellipse','rectangle'),labels_by_shape={'ellipse':'V · 全轴','rectangle':'V · 全高'})]),
  section('成像焦距',[field('system.rx.focal_length_h_mm','H · 水平'),field('system.rx.focal_length_v_mm','V · 垂直')],'mm'),
  section('PSF标准差 σ',[field('system.rx.psf_sigma_h_um','H · 水平'),field('system.rx.psf_sigma_v_um','V · 垂直')],'μm'),
  section('接收效率',['system.rx.rx_efficiency']),
  section('固定标定延迟',['system.acquisition.calibration_delay_ns'])]},
 {'module':'SPAD与读出','sections':[
  section('直方图时间窗口',[field('system.acquisition.gate_start_ns','起点 / 延迟'),field('system.acquisition.gate_width_ns','窗口长度')],'ns'),
  section('直方图时间分箱',['system.readout.tdc_bin_ps','transport.histogram_count_bits'],derived=['histogramReadout']),
  section('通道内空间 binning',[field('system.spad.H_binning','H · 水平'),field('system.spad.V_binning','V · 垂直')],'个',['binningDerived']),
  section('像元几何',['system.spad.pixel_pitch_um'],derived=['binningSize']),
  section('填充因子',['system.spad.fill_factor']),
  section('时间响应',['system.spad.spad_dead_time_ns','system.spad.spad_jitter_fwhm_ps']),
  section('数字读出',[field('system.readout.readout_mode',full=True),'system.readout.tdc_dead_time_ns'])]},
 {'module':'环境光','sections':[
  section('太阳背景',[field('system.background.solar_enabled',full=True),field('system.background.solar_illuminance_lux',when=condition('system.background.solar_enabled','true')),field('system.background.solar_reflectivity',when=condition('system.background.solar_enabled','true'))]),
  section('其他环境光',['system.background.other_light_enabled',field('system.background.other_light_scale',when=condition('system.background.other_light_enabled','true'))])]},
 {'module':'高级 · 电热与限额','sections':[
  section('列间复位',['assumptions.reset_time_ns']),
  section('电光转换',['assumptions.wall_plug_efficiency']),
  section('光功率限额',['assumptions.max_average_optical_power_w','assumptions.max_peak_optical_power_w'],'W')]},
 {'module':'电学 · SPAD输出与MIPI','sections':[
  section('输出格式',['transport.payload_format']),
  section('全Hist输出',['electrical.histogram_mode'],when=condition('transport.payload_format','histogram')),
  section('Range完整点记录',['transport.point_bytes'],when=condition('transport.payload_format','points')),
  section('Echo输出上限',['electrical.echo_max_count','electrical.echo_max_bins',field('electrical.echo_descriptor_bytes',full=True)],when=condition('transport.payload_format','echo')),
  section('片内SRAM架构',['electrical.buffer_architecture','electrical.handoff_policy'],derived=['memoryReadout']),
  section('Hist交接与清零',[field('electrical.hist_copy_us',when=condition('electrical.buffer_architecture','fixed_ab')),'electrical.bank_clear_us'],derived=['copyRateReadout']),
  section('片内DSP',['electrical.ready_delay_us',field('electrical.dsp_time_us',when=condition('transport.payload_format','points','echo'))]),
  section('输出FIFO与打包',['electrical.mipi_pack_us'],derived=['fifoReadout']),
  section('芯片与链路拓扑',['electrical.channels_per_chip','electrical.chips_per_link']),
  section('每链路 lane 容量',['electrical.data_lanes_per_link','electrical.lane_rate_mbps',field('electrical.payload_efficiency',full=True)],when=condition('electrical.capacity_mode','lanes')),
  section('MIPI容量口径',['electrical.capacity_mode',field('transport.mipi_net_mbps',when=condition('electrical.capacity_mode','aggregate_net'))]),
  section('实际硬件资源',['electrical.available_links']),
  section('应用包头',['electrical.chip_header_bytes','transport.column_header_bytes']),
  section('CSI-2长包与间隔',['electrical.packet_payload_bytes','electrical.burst_gap_us',field('electrical.line_short_packets',full=True)])]},
 {'module':'距离参考与实测对照','sections':[
  section('理想参考',['range_reference.enabled']),
  section('距离扫描范围',[field('range_reference.min_range_m','最小距离'),field('range_reference.max_range_m','最大距离')],'m',when=condition('range_reference.enabled','true')),
  section('采样与统计口径',['range_reference.points','range_reference.area_kind'],when=condition('range_reference.enabled','true'))]},
 {'module':'高级 · PRBS预算','sections':[
  section('PRBS候选',['assumptions.prbs_enabled']),
  section('编码构成',['assumptions.prbs_chip_count','assumptions.prbs_on_count'],when=condition('assumptions.prbs_enabled','true')),
  section('码片时间',['assumptions.prbs_chip_ns'],when=condition('assumptions.prbs_enabled','true'))]}
]

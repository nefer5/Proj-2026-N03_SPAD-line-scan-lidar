"""Display geometry derived from the same B optical projection as the budget.

Display layout numbers below are illustration units, never simulation defaults.
No tracing, new optical physics or photon sampling is performed here.
"""
import math
import numpy as np


def budget_schematic(cfg, optics, algorithms, single_channel=None):
    s=cfg.system;tx=s.tx;rx=s.rx;r=s.scene.range_m
    he=np.linspace(tx.angle_h_min_mrad,tx.angle_h_max_mrad,len(optics['tx_h_edges_mrad']));ve=np.linspace(tx.angle_v_min_mrad,tx.angle_v_max_mrad,len(optics['tx_v_edges_mrad']))
    fractions=np.asarray(optics['tx_energy_fraction'])
    rh=[rx.rx_angle_h_min_mrad,rx.rx_angle_h_max_mrad]
    rv=[rx.rx_angle_v_min_mrad,rx.rx_angle_v_max_mrad]
    extent=max(abs(math.tan(float(v)*1e-3)*r) for v in [*he,*ve,*rh,*rv])
    transverse_scale=4/extent  # Largest projected half-extent is four display units.
    def point(h,v):return [float(-r*math.tan(h*1e-3)*transverse_scale),float(r*math.tan(v*1e-3)*transverse_scale),8.]
    def corners(h,v):return [point(h[0],v[0]),point(h[1],v[0]),point(h[1],v[1]),point(h[0],v[1])]
    domega=np.outer(np.diff(ve),np.diff(he))*1e-6
    density=fractions/domega
    max_density=float(density.max())
    cells=[];notes=[]
    if fractions.size<=algorithms.budget_schematic_max_cells:
        for j in range(len(ve)-1):
            for i in range(len(he)-1):
                cells.append({'vertices':corners(he[i:i+2],ve[j:j+2]),'relative_density':float(density[j,i]/max_density),
                              'power_w':float(tx.pulse_average_power_w*fractions[j,i]),'fraction':float(fractions[j,i])})
    else:notes.append('Tx角格超过3D显示上限，仅显示边界；预算计算未降低采样。')
    hh,vv=np.meshgrid((he[:-1]+he[1:])/2,(ve[:-1]+ve[1:])/2)
    accepted=(hh>=rh[0])&(hh<=rh[1])&(vv>=rv[0])&(vv<=rv[1])
    viable=accepted&(fractions>0)
    index=np.unravel_index(np.argmax(np.where(viable,fractions,-1)),fractions.shape)
    target=point(float(hh[index]),float(vv[index]))
    # Device glyph positions are exploded-view layout, not a physical Tx/Rx baseline.
    source=[0.,0.,-4.];origin=[0.,0.,0.];pupil=[2.2,0.,0.];detector=[4.2,0.,0.]
    rxdata=optics['dataset']['rx']
    xe=np.asarray(rxdata['x_edges_um']);ye=np.asarray(rxdata['y_edges_um'])
    energy=np.asarray(optics['signal_energy_per_pixel_j']);ny,nx=energy.shape
    if single_channel is not None:
        energy=np.tile(energy,(s.spad.channels_v,1));ny,nx=energy.shape
        ye=(np.arange(ny+1)-ny/2)*s.spad.pixel_pitch_um
    pixel_scale=2.6/max(float(np.ptp(xe)),float(np.ptp(ye)))
    sensor_cells=[];sensor_kind='physical_pixels'
    if energy.size>algorithms.budget_schematic_max_cells:
        sensor_kind='channel_groups'
        notes.append('物理像素超过3D上限，改用通道组显示（每格为一组，不是单SPAD）。')
        energy=energy.reshape(s.spad.channels_v,s.spad.V_binning,s.spad.channels_h,s.spad.H_binning).sum(axis=(1,3))
        xe=xe[::s.spad.H_binning];ye=ye[::s.spad.V_binning]
    if energy.size<=algorithms.budget_schematic_max_cells:
        maximum=float(energy.max())
        for j in range(energy.shape[0]):
            for i in range(energy.shape[1]):
                sensor_cells.append({'center':[detector[0],
                    detector[1]+float(((ye[j]+ye[j+1])/2-(ye[0]+ye[-1])/2)*pixel_scale),detector[2]-float(((xe[i]+xe[i+1])/2-(xe[0]+xe[-1])/2)*pixel_scale)],
                    'size':[float((xe[i+1]-xe[i])*pixel_scale),float((ye[j+1]-ye[j])*pixel_scale)],
                    'relative_energy':float(energy[j,i]/maximum) if maximum else 0.,
                    'v':j,'h':i})
    else:notes.append('探测阵列超过3D显示上限，仅显示轮廓；像素与通道数量仍取真实配置。')
    def item(identifier,title,description,paths,facts):
        return {'id':identifier,'title':title,'description':description,'paths':paths,
                'facts':[{'label':label,'value':value,'unit':unit} for label,value,unit in facts]}
    components=[
        item('source','VCSEL光源 · Tx光学前','输入是全Tx角域的等效平均功率。E=P×脉宽，高斯用FWHM；不是峰值或整帧平均功率。光源形状只是符号，不表示实际发光单元布局。',
             ['system.tx.pulse_average_power_w','system.tx.pulse_fwhm_ps','system.tx.pulse_shape','system.tx.wavelength_nm','system.tx.tx_efficiency'],
             [('等效平均功率',tx.pulse_average_power_w,'W'),('单发能量',tx.total_pulse_energy_nj,'nJ'),('波长',tx.wavelength_nm,'nm'),('Tx效率',tx.tx_efficiency,'1')]),
        item('tx','Tx角分布与归一化域','红色边界是功率归一化域；远端热图表示角格积分份额除以角格立体角后的相对密度（峰值=1）。空间分布均匀；全线阵功率按V线数均分。',
             ['geometry.vfov_deg','geometry.tx_h_width_mrad'],
             [('H域全宽',float(he[-1]-he[0]),'mrad'),('V域全宽',float(ve[-1]-ve[0]),'mrad'),('单通道V全角',math.radians(cfg.geometry.vfov_deg)*1000/s.spad.channels_v,'mrad'),('单通道功率',tx.pulse_average_power_w/s.spad.channels_v,'W')]),
        item('rx','Rx · 单通道收光角域','蓝色细框标记选中通道的收光范围，淡色外框是整条阵列接收包络；信号域外不接收，背景仅在该域积分。它独立于Tx归一化域；角域重叠不等于探测效率。入瞳符号在旁侧展开，不表示真实收发基线。',
             ['rx_channel','system.rx','system.spectral_inputs.filter'],
             [('单通道H全角',cfg.rx_channel.h_width_mrad,'mrad'),('单通道V全角',math.radians(cfg.geometry.vfov_deg/s.spad.channels_v if cfg.rx_channel.v_width_deg is None else cfg.rx_channel.v_width_deg)*1000,'mrad'),('阵列V包络',rv[1]-rv[0],'mrad'),('入瞳面积',optics['budget']['aperture_area_m2']*1e6,'mm²')]),
        item('detector','SPAD阵列与读出通道','网格来自实际像素边界，颜色来自同一光学投影的探测面能量。每通道SPAD数=H_binning×V_binning；未把候选光子当作最终记录。阵列为独立放大视图。',
             ['system.spad','system.readout','system.spectral_inputs.pde'],
             [('H通道',s.spad.channels_h,'组'),('V通道',s.spad.channels_v,'组'),('每通道SPAD',s.spad.spads_per_channel,'个'),('物理像素',nx*ny,'个')]),
        item('target','目标平面与距离','远端平面位于配置距离；平面中的Tx/Rx轮廓使用R×tan(角度)投影。纵向与横向分别缩放以便阅读，不能从画面量取实际角度或尺寸。',
             ['system.scene','system.background','system.spectral_inputs.solar','system.spectral_inputs.other'],
             [('距离',r,'m'),('目标反射率',s.scene.target_reflectivity,'1'),('Tx H投影宽',float(r*(np.tan(he[-1]*1e-3)-np.tan(he[0]*1e-3))),'m'),('Tx V投影宽',float(r*(np.tan(ve[-1]*1e-3)-np.tan(ve[0]*1e-3))),'m')]),
        item('scan','转镜 / 共用角度原点','镜片是系统关系符号；锥体共用角度原点用于比较，不声明实物共轴结构。此图展示一列局部角域；HFOV是整帧扫描范围，不能当成单发Tx水平宽度。',
             ['targets','system.acquisition','system.spad.channels_v','assumptions','transport'],
             [('整帧HFOV',cfg.targets.hfov_deg,'deg'),('局部Tx H全宽',cfg.geometry.tx_h_width_mrad,'mrad'),('每列发数',s.acquisition.laser_shots,'发')])]
    aperture_w=rx.rx_aperture_mm if rx.rx_aperture_shape=='circle' else rx.rx_aperture_width_mm
    aperture_h=rx.rx_aperture_mm if rx.rx_aperture_shape=='circle' else rx.rx_aperture_height_mm
    centers=((np.linspace(tx.angle_v_min_mrad,tx.angle_v_max_mrad,s.spad.channels_v+1)[:-1]+np.linspace(tx.angle_v_min_mrad,tx.angle_v_max_mrad,s.spad.channels_v+1)[1:])/2)
    dv=(tx.angle_v_max_mrad-tx.angle_v_min_mrad)/s.spad.channels_v
    rw=dv if cfg.rx_channel.v_width_deg is None else math.radians(cfg.rx_channel.v_width_deg)*1000
    channel_regions=[{'index':i,'center_v_mrad':float(v),'tx_corners':corners([he[0],he[-1]],[v-dv/2,v+dv/2]),'rx_corners':corners([-cfg.rx_channel.h_width_mrad/2,cfg.rx_channel.h_width_mrad/2],[v-rw/2,v+rw/2]),'animation_path':[source,origin,point(0,float(v)),origin,pupil,detector]} for i,v in enumerate(centers)]
    scan_origin=[0.,-3.2,-.8]
    scan_points=[[-2*math.sin(a),-3.2,-.8+2*math.cos(a)] for a in np.linspace(-math.radians(cfg.targets.hfov_deg)/2,math.radians(cfg.targets.hfov_deg)/2,algorithms.budget_schematic_scan_samples)]
    scan_columns=[{'index':i,'h_deg':(i+.5)*cfg.targets.hfov_deg/cfg.targets.slot_count-cfg.targets.hfov_deg/2,'h_mrad':math.radians((i+.5)*cfg.targets.hfov_deg/cfg.targets.slot_count-cfg.targets.hfov_deg/2)*1000,'point':[-2*math.sin(math.radians((i+.5)*cfg.targets.hfov_deg/cfg.targets.slot_count-cfg.targets.hfov_deg/2)),-3.2,-.8+2*math.cos(math.radians((i+.5)*cfg.targets.hfov_deg/cfg.targets.slot_count-cfg.targets.hfov_deg/2))]} for i in range(cfg.targets.slot_count)] if cfg.targets.slot_count<=algorithms.budget_schematic_max_cells else []
    for i,region in enumerate(channel_regions):
        group=s.spad.channels_v-1-i if rx.mapping_mode=='inverted' else i
        w,h=float(np.ptp(xe)*pixel_scale),float(np.ptp(ye)*pixel_scale)
        y0=detector[1]-h/2+group*h/s.spad.channels_v;y1=y0+h/s.spad.channels_v
        region['detector_corners']=[[detector[0]+.03,y0,detector[2]+w/2],[detector[0]+.03,y0,detector[2]-w/2],[detector[0]+.03,y1,detector[2]-w/2],[detector[0]+.03,y1,detector[2]+w/2]]
    from .budget_views import budget_views
    views=budget_views(cfg,algorithms,centers,dv,rw,float(np.ptp(ye)))
    return {'views':views,'schema_version':3,'scan_fan':{'origin':scan_origin,'boundary':scan_points,'columns':scan_columns},'channel_regions':channel_regions,'hfov_deg':cfg.targets.hfov_deg,'slot_count':cfg.targets.slot_count,'coordinate_convention':'H_positive_is_negative_X_Z; V_positive_is_positive_Y_Z; Z_Z_forward','components':components,'tx_corners':corners([he[0],he[-1]],[ve[0],ve[-1]]),
        'rx_corners':corners(rh,rv),'tx_cells':cells,'density_label':'相对角能量密度 · 峰值=1（非探测概率）',
        'source_position':source,'origin':origin,'pupil_position':pupil,'detector_position':detector,
        'pupil_shape':rx.rx_aperture_shape,'pupil_size':[1.4*aperture_w/max(aperture_w,aperture_h),1.4*aperture_h/max(aperture_w,aperture_h)],
        'detector_cells':sensor_cells,'detector_display_kind':sensor_kind,
        'detector_size':[float(np.ptp(xe)*pixel_scale),float(np.ptp(ye)*pixel_scale)],
        'animation_path':[source,origin,target,origin,pupil,detector] if viable.any() else [source,origin,target],
        'animation_allowed':tx.pulse_average_power_w>0,
        'return_path_available':bool(viable.any()),'example_angles_mrad':[float(hh[index]),float(vv[index])],
        'scale':{'transverse_units_per_m':transverse_scale,'longitudinal_units_per_m':8/r,
                 'angular_exaggeration':transverse_scale/(8/r)},
        'note':'H正向对应−X_Z，V正向对应+Y_Z。收发共用扫描模块；器件位置为功能示意。H/V同比例、纵深压缩；动画为讲解，不是镜面求交或事件采样。',
        'display_notes':notes,'limits':{'max_cells':algorithms.budget_schematic_max_cells}}

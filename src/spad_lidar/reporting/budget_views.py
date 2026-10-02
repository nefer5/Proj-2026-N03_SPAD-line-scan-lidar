"""Presentation geometry: whole-field sweep and inspectable channel sections.

All angles are from the validated budget; SVG coordinates are layout only.
These views illustrate mappings, not a solved mirror/lens ray trace.
"""
import math
import numpy as np
from .display_numbers import display_number as fnum


def budget_views(cfg, algorithms, centers, tx_v, rx_v, detector_height_um):
    n=cfg.system.spad.channels_v
    tx_h=cfg.geometry.tx_h_width_mrad
    rx_h=cfg.rx_channel.h_width_mrad
    vf=math.radians(cfg.geometry.vfov_deg)
    hf=math.radians(cfg.targets.hfov_deg)
    sample=algorithms.budget_schematic_scan_samples
    radius=8.
    vertical_scale=max(1.,3./(radius*math.tan(vf/2)))
    def world(h,v):
        return [-radius*math.sin(h),radius*math.tan(v)*vertical_scale,radius*math.cos(h)]
    hs=np.linspace(-hf/2,hf/2,sample)
    edges=np.linspace(-vf/2,vf/2,n+1)
    surface=[[*world(float(a),-vf/2),*world(float(b),-vf/2),*world(float(b),vf/2),*world(float(a),vf/2)] for a,b in zip(hs[:-1],hs[1:])]
    full_lines=[[world(float(h),-vf/2),world(float(h),vf/2)] for h in hs]
    full_lines += [[world(float(h),float(v)) for h in hs] for v in np.linspace(-vf/2,vf/2,min(n+1,sample))]
    # Right-panel full angle chart; independent H/V layout scales are disclosed.
    columns=[]
    for i in np.unique(np.linspace(0,cfg.targets.slot_count-1,min(sample,cfg.targets.slot_count),dtype=int)):
        columns.append({'index':int(i),'x':34+264*(i+.5)/cfg.targets.slot_count})
    channels=[]
    for i in np.unique(np.linspace(0,n-1,min(n,sample),dtype=int)):
        channels.append({'index':int(i),'y':140-116*(i+1)/n,'height':116/n})
    column_regions=[]
    if cfg.targets.slot_count<=algorithms.budget_schematic_max_cells:
        for i in range(cfg.targets.slot_count):
            h=(i+.5)*hf/cfg.targets.slot_count-hf/2
            def column_quad(width,vwidth):
                half=width*1e-3/2;vh=vwidth*1e-3/2
                return [world(h-half,-vh),world(h+half,-vh),world(h+half,vh),world(h-half,vh)]
            column_regions.append({'index':i,'chart_x':34+264*(i+.5)/cfg.targets.slot_count,
                'tx_corners':column_quad(tx_h,vf*1000),
                'rx_corners':column_quad(rx_h,(n-1)*tx_v+rx_v)})
    scale=min(244/max(tx_h,rx_h),100/max(tx_v,rx_v))
    def rect(h,v):return [184-h*scale/2,82.5-v*scale/2,h*scale,v*scale]
    tx_rect,rx_rect=rect(tx_h,tx_v),rect(rx_h,rx_v)
    same=math.isclose(tx_v,rx_v,rel_tol=1e-9)
    explanation=('Rx V留空，当前跟随Tx，单通道V全角一致。' if cfg.rx_channel.v_width_deg is None else
        ('Rx V为显式输入，当前与Tx单通道V全角相同。' if same else
         f'Rx V为显式输入：{fnum(rx_v)} mrad；Tx为{fnum(tx_v)} mrad。通道中心间隔不变，因此Rx整阵列包络与Tx高度不同。'))
    details=[]
    for i,v in enumerate(centers):
        group=n-1-i if cfg.system.rx.mapping_mode=='inverted' else i
        target_y=136-108*(i+.5)/n
        detector_y=136-108*(group+.5)/n
        details.append({'index':i,'detector_group':group,'target_y':target_y,'detector_y':detector_y,
            'v_center_mrad':float(v),'v_center_deg':math.degrees(v*1e-3),
            'full_band':[[*world(float(h),float(edges[i]))] for h in hs]+[[*world(float(h),float(edges[i+1]))] for h in hs[::-1]],
            'full_chart_y':140-116*(i+1)/n,'full_chart_height':116/n})
    from ..scan.planning import uniform_column_budget
    step=uniform_column_budget(cfg.targets)['angle_per_slot_mrad']
    extent_h=max(rx_h/2,tx_h/2+step)*1.15
    def hx(angle):return 176+132*angle/extent_h
    h_profile={'ticks':[{'x':hx(float(v)),'value':float(v)} for v in np.linspace(-extent_h,extent_h,5)],
        'tx_path':[[hx(-tx_h/2),134],[hx(-tx_h/2),42],[hx(tx_h/2),42],[hx(tx_h/2),134]],
        'rx_rect':[hx(-rx_h/2),30,hx(rx_h/2)-hx(-rx_h/2),104],
        'neighbors':[[hx(center-tx_h/2),42,hx(center+tx_h/2)-hx(center-tx_h/2),92] for center in [-step,step]],
        'step_bracket':[hx(-step/2),hx(step/2)],'step_mrad':step,'rx_to_step_ratio':rx_h/step}
    envelope=(n-1)*tx_v+rx_v
    extent_v=max(vf*1000/2,envelope/2)*1.12
    def vy(angle):return 96-70*angle/extent_v
    v_profile={'ticks':[{'y':vy(float(v)),'value':float(v)} for v in np.linspace(-extent_v,extent_v,5)],
        'tx_rect':[68,vy(vf*1000/2),172,vy(-vf*1000/2)-vy(vf*1000/2)],
        'rx_envelope':[248,vy(envelope/2),24,vy(-envelope/2)-vy(envelope/2)],
        'rx_channels':[[248,vy(float(centers[row['index']])+rx_v/2),24,vy(float(centers[row['index']])-rx_v/2)-vy(float(centers[row['index']])+rx_v/2)] for row in channels]}
    return {'column_regions':column_regions,'surface':surface,'lines':full_lines,'hfov_deg':cfg.targets.hfov_deg,'vfov_deg':cfg.geometry.vfov_deg,
        'vertical_exaggeration':vertical_scale,'radius':radius,'channels':details,
        'chart':{'columns':columns,'channels':channels},'local':{'tx_rect':tx_rect,'rx_rect':rx_rect,
            'ticks_h':[{'x':184+v*scale,'value':v} for v in [-max(tx_h,rx_h)/2,0,max(tx_h,rx_h)/2]],'ticks_v':[{'y':82.5-v*scale,'value':v} for v in [-max(tx_v,rx_v)/2,0,max(tx_v,rx_v)/2]],'tx_h_mrad':tx_h,'tx_v_mrad':tx_v,'rx_h_mrad':rx_h,'rx_v_mrad':rx_v,
            'tx_h_deg':math.degrees(tx_h*1e-3),'tx_v_deg':math.degrees(tx_v*1e-3),
            'rx_h_deg':math.degrees(rx_h*1e-3),'rx_v_deg':math.degrees(rx_v*1e-3)},
        'rx_v_follows_tx':cfg.rx_channel.v_width_deg is None,'same_v_width':same,'explanation':explanation,
        'tx_v_envelope_mrad':vf*1000,'rx_v_envelope_mrad':(n-1)*tx_v+rx_v,
        'h_profile':h_profile,'v_profile':v_profile,'detector_half_height_um':detector_height_um/2,'binning_h':cfg.system.spad.H_binning,'binning_v':cfg.system.spad.V_binning}

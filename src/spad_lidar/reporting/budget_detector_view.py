"""Auditable single-channel geometry for the dual-coordinate view.

Uses the actual optical dataset's full-pixel edges and the common Rx mapping.
Display ticks are layout, not integration samples; PSF capture comes from B.
"""
import math
from types import SimpleNamespace
import numpy as np
from ..rx.spatial import image_center, image_angles


def detector_view(single_channel, dataset, algorithms):
    config=single_channel['configuration'];rx=SimpleNamespace(**config['rx']);tx=config['tx'];spad=config['spad']
    x=np.asarray(dataset['x_edges_um']);y=np.asarray(dataset['y_edges_um'])
    h,_=image_angles(rx,x,0);_,v=image_angles(rx,0,y)
    bounds={'h_min':float(h.min()),'h_max':float(h.max()),'v_min':float(v.min()),'v_max':float(v.max())}
    def domain(part,prefix):
        return dict(h_min=part[prefix+'angle_h_min_mrad'],h_max=part[prefix+'angle_h_max_mrad'],
                    v_min=part[prefix+'angle_v_min_mrad'],v_max=part[prefix+'angle_v_max_mrad'])
    tx_bounds=domain(tx,'');rx_bounds=domain(config['rx'],'rx_')
    extent=max(abs(z) for domain_ in [bounds,tx_bounds,rx_bounds] for z in domain_.values())
    # Nice, equal-angle tick spacing for a square plot; no optical resampling.
    raw=extent/5;unit=10**math.floor(math.log10(raw));step=next(z*unit for z in [1,2,5,10] if z*unit>=raw)
    limit=math.ceil(extent/step)*step
    values=np.arange(-round(limit/step),round(limit/step)+1)*step
    ticks=[dict(angle_mrad=float(a),image_x_um=float(image_center(rx,a,0)[0]),
                image_y_um=float(image_center(rx,0,a)[1])) for a in values]
    cells=[];full_cells=(len(x)-1)*(len(y)-1)
    if full_cells<=algorithms.budget_schematic_max_cells:
        for j in range(len(y)-1):
            for i in range(len(x)-1):
                cells.append(dict(h_index=i,v_index=j,h_min=float(min(h[i:i+2])),h_max=float(max(h[i:i+2])),
                                  v_min=float(min(v[j:j+2])),v_max=float(max(v[j:j+2]))))
    b=single_channel['optical_budget'];after=b['after_filter_fullplane_signal_j'];sensor=b['sensor_signal_j']
    return dict(tx_bounds=tx_bounds,rx_bounds=rx_bounds,binning_bounds=bounds,cells=cells,
        cell_count=full_cells,cells_omitted=not cells,ticks=ticks,angle_limits_mrad=[-limit,limit],tick_step_mrad=step,
        pixel_x_edges_um=x.tolist(),pixel_y_edges_um=y.tolist(),cell_h_edges_mrad=h.tolist(),cell_v_edges_mrad=v.tolist(),
        detector_h_um=float(np.ptp(x)),detector_v_um=float(np.ptp(y)),binning_h=spad['H_binning'],binning_v=spad['V_binning'],
        pixel_pitch_um=spad['pixel_pitch_um'],mapping_mode=rx.mapping_mode,
        focal_length_h_mm=rx.focal_length_h_mm,focal_length_v_mm=rx.focal_length_v_mm,
        offset_x_um=rx.rx_offset_x_um,offset_y_um=rx.rx_offset_y_um,
        tx_h_mrad=tx_bounds['h_max']-tx_bounds['h_min'],tx_v_mrad=tx_bounds['v_max']-tx_bounds['v_min'],
        rx_h_mrad=rx_bounds['h_max']-rx_bounds['h_min'],rx_v_mrad=rx_bounds['v_max']-rx_bounds['v_min'],
        detector_h_mrad=bounds['h_max']-bounds['h_min'],detector_v_mrad=bounds['v_max']-bounds['v_min'],
        tx_h_deg=math.degrees((tx_bounds['h_max']-tx_bounds['h_min'])*1e-3),tx_v_deg=math.degrees((tx_bounds['v_max']-tx_bounds['v_min'])*1e-3),
        rx_h_deg=math.degrees((rx_bounds['h_max']-rx_bounds['h_min'])*1e-3),rx_v_deg=math.degrees((rx_bounds['v_max']-rx_bounds['v_min'])*1e-3),
        capture_fraction=sensor/after if after>0 else None,
        source='single-channel B dataset full-pixel edges; common Rx image_center inverse; B PSF-integrated capture',
        note='一个独立角通道。框线不强制对齐；灰色虚线为等角度网格，绿色实线为实际cell边界。像面副轴按精确成像映射，非ZMAX全局轴。PDE/FF尚未作用。')

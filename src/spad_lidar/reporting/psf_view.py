"""PSF-only parameter figures, independent of the channel-layout projection view."""
import numpy as np
from ..rx.spatial import psf_orders,psf_axis_mass
from ..numerics.spatial_profiles import scale_from_sigma,profile_density


def psf_parameter_figure(optics,algorithms,pixel_psf,x_edges,y_edges):
    if algorithms.psf_preview_samples**2>algorithms.max_optical_cells:
        raise ValueError('PSF preview exceeds max_optical_cells before allocation')
    synthetic=optics.rx_model in ('gaussian_psf','super_gaussian_psf')
    if synthetic:
        extent=algorithms.psf_preview_extent_sigma;n=algorithms.psf_preview_samples
        xe=np.linspace(-extent*optics.psf_sigma_h_um,extent*optics.psf_sigma_h_um,n+1)
        ye=np.linspace(-extent*optics.psf_sigma_v_um,extent*optics.psf_sigma_v_um,n+1)
        x=(xe[:-1]+xe[1:])/2;y=(ye[:-1]+ye[1:])/2;mh,mv=psf_orders(optics)
        px=profile_density(x,scale_from_sigma(optics.psf_sigma_h_um,mh),mh)
        py=profile_density(y,scale_from_sigma(optics.psf_sigma_v_um,mv),mv)
        density=np.outer(py,px)
        captured=float(psf_axis_mass(xe,optics.psf_sigma_h_um,mh).sum()*psf_axis_mass(ye,optics.psf_sigma_v_um,mv).sum())
        note='独立 PSF 形状，以自身中心为原点；σ 为实际标准差，H/V 可分别设定。显示窗裁切不重新归一化。通道投影另见下方光学响应区。'
        facts=[['σ_H',optics.psf_sigma_h_um,'μm'],['σ_V',optics.psf_sigma_v_um,'μm'],['m_H',mh,''],['m_V',mv,''],['显示窗积分',captured,'']]
        title='PSF 自身分布 · H/V 边缘密度';x_label='相对 PSF 中心 / μm'
    else:
        mass=np.asarray(pixel_psf);xe=np.asarray(x_edges);ye=np.asarray(y_edges)
        total=mass.sum();tail=(1-algorithms.psf_preview_retained_fraction)/2
        def crop(marginal):
            if total==0:return slice(0,len(marginal))
            cdf=np.cumsum(marginal)/total
            lo=int(np.searchsorted(cdf,tail,side='right'));hi=min(len(marginal),int(np.searchsorted(cdf,1-tail))+1)
            return slice(min(lo,len(marginal)-1),hi)
        xs=crop(mass.sum(axis=0));ys=crop(mass.sum(axis=1))
        px=(mass.sum(axis=0)/np.diff(xe))[xs];py=(mass.sum(axis=1)/np.diff(ye))[ys]
        xe=xe[xs.start:xs.stop+1];ye=ye[ys.start:ys.stop+1]
        x=(xe[:-1]+xe[1:])/2;y=(ye[:-1]+ye[1:])/2
        density=mass[ys,xs]/np.outer(np.diff(ye),np.diff(xe))
        note='保存的有限像面 PSF 采样：按像素面积/宽度换算平均密度，聚焦主要响应区域；不外推、不补偿阵列外损失，不叠加通道标记。'
        facts=[['原采样面截获份额',float(total),''],['显示区积分',float(mass[ys,xs].sum()),'']]
        title='PSF 独立采样分布 · H/V 边缘密度';x_label='像面位置 / μm'
    def series(label,x,y,color,marker,offset):
        stride=max(1,len(x)//12)  # Marker spacing is layout only; every value stays in the curve.
        indices=np.arange(offset if len(x)>offset else 0,len(x),stride)
        return {'label':label,'x':x.tolist(),'y':y.tolist(),'color':color,'dash':[6,4] if marker=='circle' else [2,4],
                'marker':marker,'points_x':x[indices].tolist(),'points_y':y[indices].tolist()}
    return {'title':title,'x_label':x_label,'y_label':'边缘概率密度 / μm⁻¹','heatmap':'psf',
        'series':[series('H / x · 圆点虚线',x,px,'cyan','circle',0),series('V / y · 菱点虚线',y,py,'amber','diamond',2)],
        'note':note+' 同宽时两曲线可重合；交错圆点/菱点和不同虚线用于区分，数据没有平移。',
        'facts':facts,'psf_map':{'values':density.tolist(),'x_edges_um':xe.tolist(),'y_edges_um':ye.tolist(),
                              'x_label':x_label,'y_label':'相对中心 y / μm' if synthetic else '像面 y / μm','color_label':'μm⁻²'},
        'preview_policy':{key:getattr(algorithms,key) for key in ('psf_preview_samples','psf_preview_extent_sigma','psf_preview_retained_fraction')}}

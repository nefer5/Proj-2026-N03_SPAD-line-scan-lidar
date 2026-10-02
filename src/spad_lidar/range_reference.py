"""Ideal single-channel ranging reference; empirical points are comparisons only."""
import math
import numpy as np
from .constants import C
from .numerics.ideal_irf import IdealIRF


def range_reference(cfg,budget,a):
    s=cfg.system;r=cfg.range_reference
    irf=IdealIRF(s.tx.pulse_shape,s.tx.pulse_fwhm_ps,math.hypot(s.spad.spad_jitter_fwhm_ps,s.readout.other_jitter_fwhm_ps))
    bin_ns=s.readout.tdc_bin_ps*1e-3;gate_start=s.acquisition.gate_start_ns;gate_end=gate_start+s.acquisition.gate_width_ns
    shots=s.acquisition.laser_shots
    background_rate=(budget['solar_candidate_rate_cps']+budget['other_candidate_rate_cps']+
        s.spad.spads_per_channel*(s.spad.dcr_cps_per_spad+s.spad.other_noise_cps_per_spad))
    bg_area=background_rate*s.acquisition.gate_width_ns*1e-9*shots
    signal_at_reference=budget['signal_candidate_avalanches_per_pulse']*shots
    support=irf.support_ns(a.budget_reference_sigma_extent)
    def evaluate(distance,with_histogram=False):
        center=2*distance/C*1e9+s.acquisition.calibration_delay_ns
        strength=signal_at_reference*(s.scene.range_m/distance)**2
        fraction=float(irf.cdf(gate_end-center)-irf.cdf(gate_start-center))
        lo=max(gate_start,center-support);hi=min(gate_end,center+support)
        edges=np.array([])
        if hi>lo:
            first=max(0,math.floor((lo-gate_start)/bin_ns));last=math.ceil((hi-gate_start)/bin_ns)
            if last-first>a.budget_reference_max_bins:raise ValueError('Ideal histogram ROI exceeds reference bin limit; increase TDC bin or change algorithm limit explicitly')
            edges=gate_start+np.arange(first,last+1)*bin_ns
            edges[-1]=min(edges[-1],gate_end)
        peak=0.;peak_total=background_rate*bin_ns*1e-9*shots;info=0.;bias=None;hist=None
        if edges.size>1:
            p=np.maximum(0,irf.cdf(edges[1:]-center)-irf.cdf(edges[:-1]-center))
            dp=irf.pdf(edges[:-1]-center)-irf.pdf(edges[1:]-center)
            signal=strength*p;bg=background_rate*np.diff(edges)*1e-9*shots;mu=signal+bg
            usable=mu>0
            itt=float(np.sum((strength*dp[usable])**2/mu[usable]))
            iaa=float(np.sum(p[usable]**2/mu[usable]));ita=float(np.sum(strength*dp[usable]*p[usable]/mu[usable]))
            info=itt-ita*ita/iaa if iaa>0 else 0.
            peak=float(signal.max());peak_total=float(mu.max())
            if signal.sum()>0:bias=float((np.dot(signal,(edges[:-1]+edges[1:])/2)/signal.sum()-center)*C*.5e-6)
            if with_histogram:hist={'relative_ns':(((edges[:-1]+edges[1:])/2)-center).tolist(),'signal_counts':signal.tolist(),'total_counts':mu.tolist(),'bin_width_ns':np.diff(edges).tolist()}
        sigma_mm=None if info<=0 else C*.5e-6/math.sqrt(info)
        row={'distance_m':distance,'center_ns':center,'signal_area_counts':strength*fraction,'total_area_counts':strength*fraction+bg_area,
            'peak_signal_counts':peak,'peak_total_counts':peak_total,'irf_fwhm_ns':irf.fwhm_ns(),'gate_fraction':fraction,
            'precision_crlb_mm':sigma_mm,'gate_centroid_bias_mm':bias,'fisher_delay_per_ns2':max(0.,info)}
        if with_histogram:row['histogram']=hist
        return row
    curves=[evaluate(float(distance)) for distance in np.linspace(r.min_range_m,r.max_range_m,r.points)]
    measurements=r.manual_points if r.measurement_mode=='manual' else r.csv_points
    return {'points':curves,'current':evaluate(s.scene.range_m,True),'measurements':[p.model_dump() for p in measurements],
        'area_kind':r.area_kind,'measurement_mode':r.measurement_mode,'background_area_counts':bg_area,
        'note':'单角通道、一列内多发累计；满角域朗伯目标，固定反射率/光学效率/大气透过率，信号按公共B核当前值作1/R²理想缩放。激光脉冲与SPAD/其他高斯抖动卷积，按实际TDC bin和gate积分。精度为独立泊松候选直方图的延时Fisher下限，幅值未知作为干扰参数，背景视为已知；不是实测标定或估计器效果。不含死时间、pile-up、TDC容量、扫描、温漂或时钟系统误差。实测点仅对照，不自动改正距离或拟合标定参数。',
        'sources':['https://opg.optica.org/ao/abstract.cfm?uri=ao-47-28-5147','https://pmc.ncbi.nlm.nih.gov/articles/PMC12526853/']}

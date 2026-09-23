"""C composition: pulse schedule → B optics at emission/return poses → one SPAD session."""
import numpy as np
from pydantic import model_validator
from ..constants import C,H
from ..curves import Curve
from ..contracts.pulses import IncidentPulseGroup
from ..scan.config import ScanTiming,ScanSettings,SceneMotion
from ..scan.schedule import build_schedule
from ..scan.trajectory import mirror_pose
from ..scene.scan_target import reflection_range
from ..rx.budget import aperture_area
from ..rx.projection import project_return
from ..adapters.optical_data import RxTable,RxData
from ..tx import transmit
from ..numerics.temporal import pulse_interval_fractions
from ..spad.source import sample_varying_candidates
from ..spad.device import effective_pde
from .spatial import SystemConfig,project_illumination
from .lab import acquire_candidates,stamp_result


class ScanConfig(SystemConfig):
    timing: ScanTiming
    scan: ScanSettings
    scene_motion: SceneMotion

    @model_validator(mode='after')
    def scan_valid(self):
        n=self.optics.channels_h*self.optics.channels_v
        if not all(np.all(np.isfinite(v)) for v in (self.scan.channel_h_mrad,self.scan.channel_v_mrad)):
            raise ValueError('Channel calibration angles must be finite')
        if self.scan.channel_direction_mode=='explicit' and (len(self.scan.channel_h_mrad)!=n or len(self.scan.channel_v_mrad)!=n):
            raise ValueError('Explicit direction calibration requires one H/V pair per readout channel')
        return self


class PulseProjection:
    def __init__(self,cfg,a,light,groups,info,schedule):
        self.cfg=cfg;self.a=a;self.light=light;self.groups=groups;self.info=info
        self.rows={r['cycle']:r for r in schedule}
        self.h=np.asarray(info['angular_h_centers_mrad']);self.v=np.asarray(info['angular_v_centers_mrad'])
        self.fractions=np.asarray(info['tx_energy_fraction']).ravel()
        self.shape=np.asarray(info['tx_energy_fraction']).shape
        emitted_count=sum(row['emitted'] for row in schedule)
        if emitted_count*len(self.h)*len(groups)>a.max_scan_projection_work:
            raise ValueError('Estimated pulse × angle × pixel work exceeds max_scan_projection_work')
        components=1 if cfg.scene_motion.range_gradient_m_per_rad==0 else self.shape[1]
        sampling_work=(emitted_count*components+(len(schedule)-emitted_count)+len(schedule))*len(groups)
        if sampling_work>a.max_scan_sampling_work:
            raise ValueError('Estimated photon component/pixel sampling exceeds max_scan_sampling_work')
        self.table=RxTable(RxData.model_validate(info['dataset']['rx']))
        self.area=aperture_area(cfg.optics)
        self.emitted=transmit(cfg.optics.total_pulse_energy_nj*1e-9,cfg.optics.tx_efficiency)
        self.filter_at=Curve(cfg.spectral_inputs.filter)(cfg.optics.wavelength_nm)
        self.photon_j=H*C/(cfg.optics.wavelength_nm*1e-9)
        self.channels=cfg.optics.channels_h*cfg.optics.channels_v
        self.work=0;self.trace=[];self.components=[]
        self.accumulated_pixels=np.zeros(len(groups));self.emission_count=0
        self.signal_response=float(effective_pde(Curve(cfg.spectral_inputs.pde)(cfg.optics.wavelength_nm),cfg.device.fill_factor))
        self.budget_totals={k:0. for k in ('target_incident_j','target_reflected_j','pupil_j','after_rx_j','after_filter_j','sensor_j','rx_loss_j','filter_loss_j','edge_loss_j')}
        self.truth={}
        self.static_equivalent=(cfg.scan.trajectory=='static' and cfg.scan.rx_scan_scale==1 and cfg.scan.rx_angle_offset_mrad==0
            and cfg.scene_motion.range_gradient_m_per_rad==0 and cfg.scene_motion.radial_velocity_m_s==0)

    def __call__(self,window):
        row=self.rows[window.cycle];cfg=self.cfg;o=cfg.optics;s=cfg.scan
        if not row['emitted']:
            if window.measured:
                self.trace.append({'cycle':window.cycle,'emitted':False,'sensor_photons':0.,'energy_balance_residual_j':0.})
                self.components.append({'cycle':window.cycle,'arrival_centers_ns':[],
                    'signal_photons_per_component_per_pixel':[], 'signal_photons_per_pixel':np.zeros(len(self.groups)).tolist()})
            return IncidentPulseGroup(np.zeros((1,len(self.groups))),np.array([o.wavelength_nm]),
                                      np.array([row['emission_time_ns']+self.light.pulse_delay_ns]),o.pulse_shape,o.pulse_fwhm_ps)
        self.work+=len(self.h)*len(self.groups)
        if self.work>self.a.max_scan_projection_work:
            raise ValueError('Pulse × angle × pixel projection exceeds max_scan_projection_work')
        world_h=self.h+row['true_tx_optical_mrad']
        if not np.all(np.isfinite(world_h)) or np.any(np.abs(world_h)>self.a.max_spatial_angle_mrad):
            raise ValueError('Global emitted ray angle exceeds configured paraxial domain')
        ranges=reflection_range(o,cfg.scene_motion,world_h,row['emission_time_ns'])
        echo_time=row['emission_time_ns']+2*ranges/C*1e9
        _,rx_pose,_,_=mirror_pose(s,echo_time)
        rx_pose=rx_pose*s.rx_scan_scale+s.rx_angle_offset_mrad
        relative_h=world_h-rx_pose
        if self.static_equivalent:
            # Exact coordinate cancellation avoids floating round-off at database boundaries.
            relative_h=self.h.copy()
        eff,psf=self.table.evaluate(o.wavelength_nm,relative_h,self.v)
        psf=psf.reshape(len(self.h),len(self.groups))
        projection=project_return(self.emitted*self.fractions,o.atmospheric_one_way_transmission,o.target_reflectivity,
                                  self.area,ranges,o.overlap_factor,eff,self.filter_at,psf)
        ray_photons=projection.after_filter[:,None]*psf/self.photon_j
        if cfg.scene_motion.range_gradient_m_per_rad==0:
            signal=(projection.pixel_energy/self.photon_j)[None,:]
            centers=np.array([echo_time[0]+o.calibration_delay_ns])
            if self.static_equivalent:
                signal=self.light.signal_photons_per_pulse.sum(axis=1)[None,:]
        else:
            # Range varies only with H; V rays share an arrival center and can be combined exactly.
            signal=ray_photons.reshape(*self.shape,len(self.groups)).sum(axis=0)
            centers=echo_time.reshape(self.shape)[0]+o.calibration_delay_ns
        sensor_j=float(projection.pixel_energy.sum())
        totals={'target_incident_j':float(projection.target_incident.sum()),'target_reflected_j':float(projection.target_reflected.sum()),
                'pupil_j':float(projection.pupil.sum()),'after_rx_j':float(projection.after_rx.sum()),
                'after_filter_j':float(projection.after_filter.sum()),'sensor_j':sensor_j,
                'rx_loss_j':float(projection.pupil.sum()-projection.after_rx.sum()),
                'filter_loss_j':float(projection.after_rx.sum()-projection.after_filter.sum()),
                'edge_loss_j':float(projection.after_filter.sum()-sensor_j)}
        if window.measured:
            self.emission_count+=1;self.accumulated_pixels+=signal.sum(axis=0)
            for key,value in totals.items():self.budget_totals[key]+=value
            channel_weights=np.column_stack([ray_photons[:,self.groups==ch].sum(axis=1) for ch in range(self.channels)])
            self.truth[window.cycle]={'photons':channel_weights.sum(axis=0),
                'range_weighted':ranges@channel_weights,'h_weighted':world_h@channel_weights,'v_weighted':self.v@channel_weights}
            residual=totals['pupil_j']-sum(totals[k] for k in ('sensor_j','rx_loss_j','filter_loss_j','edge_loss_j'))
            self.trace.append({'cycle':window.cycle,'emitted':True,**totals,'sensor_photons':float(signal.sum()),
                'energy_balance_residual_j':residual,'ray_reflection_ranges_m':ranges.tolist(),
                'ray_echo_time_ns':echo_time.tolist(),'rx_pointing_at_echo_mrad':rx_pose.tolist(),
                'ray_relative_rx_h_mrad':relative_h.tolist(),'ray_psf_capture_fraction':psf.sum(axis=1).tolist()})
            self.components.append({'cycle':window.cycle,'arrival_centers_ns':centers.tolist(),
                                    'signal_photons_per_component_per_pixel':signal.tolist(),
                                    'signal_photons_per_pixel':signal.sum(axis=0).tolist()})
        return IncidentPulseGroup(signal,np.full(len(centers),o.wavelength_nm),centers,o.pulse_shape,o.pulse_fwhm_ps)


def channel_directions(cfg,info):
    if cfg.scan.channel_direction_mode=='explicit':
        return list(zip(cfg.scan.channel_h_mrad,cfg.scan.channel_v_mrad))
    from ..adapters.optical_data import RxData
    rx=RxTable(RxData.model_validate(info['dataset']['rx']))
    h=np.array(info['angular_h_centers_mrad']);v=np.array(info['angular_v_centers_mrad'])
    eff,_=rx.evaluate(cfg.optics.wavelength_nm,h,v)
    he=np.array(info['tx_h_edges_mrad']);ve=np.array(info['tx_v_edges_mrad'])
    omega=np.outer(np.diff(ve),np.diff(he)).ravel()*1e-6
    weights=np.asarray(info['angle_to_channel_fraction'])*(eff*omega)[:,None]
    output=[]
    for w in weights.T:
        output.append((float(h@w/w.sum()),float(v@w/w.sum())) if w.sum()>0 else (None,None))
    return output


def run_scan(cfg,a,progress,cancelled):
    program,schedule,edges,frame_budget=build_schedule(cfg,a)
    light,groups,info=project_illumination(cfg,a,progress,cancelled)
    projector=PulseProjection(cfg,a,light,groups,info,schedule)
    streams=np.random.SeedSequence(cfg.rng_seed).spawn(3)
    candidates,source_audit=sample_varying_candidates(projector,light,cfg.device,Curve(cfg.spectral_inputs.pde),program,
        np.random.default_rng(streams[0]),a.max_readout_events_per_run,a.max_scan_sampling_work,progress,cancelled)
    result=acquire_candidates(cfg,a,candidates,source_audit,groups,program,streams[1],progress,cancelled)
    measured=[r for r in schedule if r['measured']]
    directions=channel_directions(cfg,info)
    from ..processing.scan_reconstruction import reconstruct_scan
    reconstruction=reconstruct_scan(cfg,a,result['records'],schedule,edges,directions,projector.truth)
    average=projector.accumulated_pixels/projector.emission_count if projector.emission_count else np.zeros(len(groups))
    result['illumination']={'signal_photons_per_pixel_per_pulse':average.tolist(),
        'background_photons_per_pixel_per_second':light.background_photons_per_second.sum(axis=1).tolist(),
        'shape':info['array_shape'],'provenance':{**light.provenance,'kind':'scan_mean_per_emitted_pulse',
        'normalization':'Mean over emitted measured reference slots, excluding blanked slots and warmup.'}}
    info['reference_role']='Static B reference at configured base range; actual C pulse projections and totals are in scan.'
    result['optics']=info
    gate_exposure_s=sum(w.gate_close_ns-w.gate_open_ns for w in program.windows if w.measured)*1e-9
    actual_count=sum(r['emitted'] and 0<=r['emission_time_ns']<frame_budget['duration_ns'] for r in schedule)
    fractions=pulse_interval_fractions([r['emission_time_ns'] for r in schedule],0,frame_budget['duration_ns'],cfg.optics.pulse_shape,cfg.optics.pulse_fwhm_ps)
    for row,fraction in zip(schedule,fractions):
        row['tx_energy_fraction_in_measurement_window']=float(fraction) if row['emitted'] else 0.
    time_window_energy=sum(r['tx_energy_fraction_in_measurement_window'] for r in schedule)*projector.emitted
    frame_budget.update(actual_emissions_in_time_window=actual_count,
        reference_enabled_rate_hz=projector.emission_count/(frame_budget['duration_ns']*1e-9),
        actual_emission_rate_hz=actual_count/(frame_budget['duration_ns']*1e-9),
        center_accounted_tx_output_energy_j=actual_count*projector.emitted,
        actual_tx_output_energy_j=time_window_energy,
        actual_tx_average_power_w=time_window_energy/(frame_budget['duration_ns']*1e-9))
    result['scan']={'schedule':measured,'warmup_schedule':[r for r in schedule if not r['measured']],
       'frame_budget':frame_budget,'angle_edges_mrad':edges.tolist(),'channel_directions_mrad':directions,
       'channel_direction_method':cfg.scan.channel_direction_mode,'projection_work':projector.work,
       'pulse_optical_audit':projector.trace,'signal_components':projector.components,
       'source_truth_by_cycle':{str(k):{name:value.tolist() for name,value in row.items()} for k,row in projector.truth.items()},
       'recording_gate_exposure_s':gate_exposure_s,'signal_budget_total':projector.budget_totals,
       **reconstruction,
       'assumptions':['水平周期转镜、显式机械→光学角映射。',
          '在脉冲中心和各角单元回波中心求姿态，尚未解析脉宽内连续角运动。',
          '背景在接收机局部角域均匀平稳；回扫关光不复位SPAD/TDC或关闭周期门。',
          '构造径向距离场使用局部正入射朗伯近似；无遮挡、横向目标运动或多普勒谱移。',
          '帧/角标签来自触发参考与编码器，不读取隐藏的光子来源身份。',
          '距离线图和点云未经检测门限判定，没有C专用Pd/PFA标定。']}
    from ..processing.spatial_ranges import estimate_channels
    result['channel_ranges']=estimate_channels(cfg,a,result['histogram'])
    from ..reporting.scan_flow import build_scan_flow
    result['photon_flow']=build_scan_flow(cfg,info,projector,result,gate_exposure_s)
    result=stamp_result('C_pulse_resolved_scan',cfg,a,result)
    result['provenance']['sampling_protocol']='per-reference-cycle-per-component-per-pixel-v1'
    result['provenance']['rng_streams']={'photons':[0],'electronics':[1],'laser_timing':[2]}
    return result

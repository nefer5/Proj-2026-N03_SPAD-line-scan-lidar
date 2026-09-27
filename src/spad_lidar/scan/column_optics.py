"""Wide world yaw, local B receiver coordinates, and shared optical energy kernels."""
from collections import OrderedDict
import numpy as np
from ..constants import C,H
from ..curves import Curve
from ..contracts.pulses import IncidentPulseGroup
from ..adapters.optical_data import RxTable,RxData
from ..rx.budget import aperture_area
from ..rx.projection import project_return
from ..rx.response import ReceiverResponse
from ..scene.scan_target import reflection_range
from ..tx import transmit
from .trajectory import mirror_pose


def yaw_angles(h_mrad,v_mrad,yaw_mrad):
    """Rotate local projective ray angles; preserves vertical geometry at wide yaw."""
    x=np.tan(np.asarray(h_mrad)*1e-3);y=np.tan(np.asarray(v_mrad)*1e-3)
    angle=np.asarray(yaw_mrad)*1e-3
    z=np.cos(angle)-np.sin(angle)*x
    xx=np.cos(angle)*x+np.sin(angle)
    return np.arctan2(xx,z)*1e3,np.arctan2(y,z)*1e3


class ColumnPulseProjection:
    def __init__(self,cfg,a,light,groups,info,schedule):
        self.cfg=cfg;self.a=a;self.light=light;self.groups=np.asarray(groups);self.info=info
        self.rows={r['cycle']:r for r in schedule}
        self.h=np.array(info['angular_h_centers_mrad']);self.v=np.array(info['angular_v_centers_mrad'])
        self.fractions=np.array(info['tx_energy_fraction']).ravel()
        self.shape=np.array(info['tx_energy_fraction']).shape
        count=sum(r['emitted'] for r in schedule)
        if count*len(self.h)*len(groups)>a.max_column_projection_work:raise ValueError('Column optical projection exceeds configured work limit')
        self.table=ReceiverResponse(RxData.model_validate(info['dataset']['rx']),cfg.optics,a)
        self.area=aperture_area(cfg.optics);self.filter_at=Curve(cfg.spectral_inputs.filter)(cfg.tx.wavelength_nm)
        self.photon_j=H*C/(cfg.tx.wavelength_nm*1e-9)
        self.channels=cfg.spad.channels_h*cfg.spad.channels_v
        self.group_mask=np.equal(np.arange(self.channels)[:,None],self.groups[None,:])
        self.trace=[];self.truth={};self.cache=OrderedDict();self.work=0;self.cache_hits=0
        self.pixel_photons=np.zeros(len(groups));self.budget_totals={k:0. for k in
            ('target_incident_j','target_reflected_j','pupil_j','after_rx_j','after_filter_j','sensor_j','rx_loss_j','filter_loss_j','edge_loss_j')}

    def _relative_yaw(self,row,flight):
        s=self.cfg.scan;t=row['emission_time_ns'];_,rx,_,_=mirror_pose(s,t+flight)
        # Algebraically eliminate the large common world angle for uniform motion.
        # This is exact within one linear branch, not an approximation across turns.
        move=rx-row['true_tx_optical_mrad']
        if s.trajectory=='sawtooth':
            period=self.cfg.budget['frame_period_ns'];phase=(t+s.phase_offset_ns)%period
            end=self.cfg.budget['scan_allocatable_ns'] if phase<self.cfg.budget['scan_allocatable_ns'] else period
            if np.all(phase+flight<end):move=row['optical_velocity_mrad_per_ns']*flight
        delta=(1-s.rx_scan_scale)*row['true_tx_optical_mrad']-s.rx_scan_scale*move-s.rx_angle_offset_mrad
        return delta,rx*s.rx_scan_scale+s.rx_angle_offset_mrad

    def evaluate(self,row):
        cfg=self.cfg;o=cfg.optics
        world_h,world_v=yaw_angles(self.h,self.v,row['true_tx_optical_mrad'])
        if not np.all(np.isfinite(world_h)) or not np.all(np.isfinite(world_v)):
            raise ValueError('Nonfinite world ray direction')
        ranges=reflection_range(o,cfg.scene_motion,world_h,row['emission_time_ns'])
        flight=2*ranges/C*1e9;delta,rx_axis=self._relative_yaw(row,flight)
        relative_h,relative_v=yaw_angles(self.h,self.v,delta)
        if np.all(delta==0):relative_h=self.h.copy();relative_v=self.v.copy()
        if np.any(np.abs(relative_h)>self.a.max_spatial_angle_mrad) or np.any(np.abs(relative_v)>self.a.max_spatial_angle_mrad):
            raise ValueError('Receiver-local incidence exceeds the configured optical model domain')
        key=(ranges.tobytes(),relative_h.tobytes(),relative_v.tobytes())
        if key in self.cache:
            self.cache_hits+=1;unit=self.cache.pop(key);self.cache[key]=unit
        else:
            self.work+=len(self.h)*len(self.groups)
            eff,psf=self.table.evaluate(o.wavelength_nm,relative_h,relative_v)
            psf=psf.reshape(len(self.h),len(self.groups))
            projection=project_return(transmit(1.,o.tx_efficiency)*self.fractions,o.atmospheric_one_way_transmission,
                o.target_reflectivity,self.area,ranges,o.overlap_factor,eff,self.filter_at,psf)
            photons=projection.after_filter[:,None]*psf/self.photon_j
            totals={'target_incident_j':float(projection.target_incident.sum()),'target_reflected_j':float(projection.target_reflected.sum()),
                'pupil_j':float(projection.pupil.sum()),'after_rx_j':float(projection.after_rx.sum()),
                'after_filter_j':float(projection.after_filter.sum()),'sensor_j':float(projection.pixel_energy.sum()),
                'rx_loss_j':float(projection.pupil.sum()-projection.after_rx.sum()),
                'filter_loss_j':float(projection.after_rx.sum()-projection.after_filter.sum()),
                'edge_loss_j':float(projection.after_filter.sum()-projection.pixel_energy.sum())}
            unit=(photons,photons@self.group_mask.T,totals,psf.sum(axis=1))
            self.cache[key]=unit
            if len(self.cache)>self.a.column_projection_cache_entries:self.cache.popitem(last=False)
        photon_basis,channel_basis,total_basis,capture=unit
        energy=row['energy_nj']*1e-9;photons=photon_basis*energy;channel=channel_basis*energy
        totals={k:v*energy for k,v in total_basis.items()}
        return dict(photons=photons,channel=channel,totals=totals,world_h=world_h,world_v=world_v,
            ranges=ranges,arrival_ns=row['emission_time_ns']+flight,rx_axis=rx_axis,
            relative_h=relative_h,relative_v=relative_v,capture=capture)

    def __call__(self,window):
        row=self.rows[window.cycle];cfg=self.cfg;o=cfg.optics
        tail=None if cfg.exposure.tail_fraction==0 else (cfg.exposure.tail_fraction,cfg.exposure.tail_tau_ns)
        if not row['emitted']:
            return IncidentPulseGroup(np.zeros((1,len(self.groups))),np.array([o.wavelength_nm]),
                np.array([row['emission_time_ns']+self.light.pulse_delay_ns]),o.pulse_shape,o.pulse_fwhm_ps,tail)
        out=self.evaluate(row)
        # Preserve each angular flight-time component when the scene varies by angle.
        if cfg.scene_motion.range_gradient_m_per_rad==0:
            signal=out['photons'].sum(axis=0)[None,:];centers=np.array([out['arrival_ns'][0]])
        else:
            signal=out['photons'].reshape(*self.shape,len(self.groups)).sum(axis=0)
            centers=out['arrival_ns'].reshape(self.shape)[0]
        centers=centers+o.calibration_delay_ns
        self.truth[row['cycle']]={'photons':out['channel'].sum(axis=0),
            'range_weighted':out['ranges']@out['channel'],'h_weighted':out['world_h']@out['channel'],
            'v_weighted':out['world_v']@out['channel']}
        self.trace.append({'cycle':row['cycle'],'column_id':row['column_id'],'measured':row['measured'],
            'input_energy_j':row['energy_nj']*1e-9,**out['totals'],'sensor_photons':float(signal.sum()),
            'energy_balance_residual_j':out['totals']['pupil_j']-sum(out['totals'][k] for k in ('sensor_j','rx_loss_j','filter_loss_j','edge_loss_j')),
            'range_min_m':float(out['ranges'].min()),'range_max_m':float(out['ranges'].max()),
            'rx_at_return_min_mrad':float(out['rx_axis'].min()),'rx_at_return_max_mrad':float(out['rx_axis'].max()),
            'relative_h_min_mrad':float(out['relative_h'].min()),'relative_h_max_mrad':float(out['relative_h'].max()),
            'channel_photons':out['channel'].sum(axis=0).tolist()})
        if row['measured']:
            total=out['totals'];self.pixel_photons+=signal.sum(axis=0)
            for k,v in total.items():self.budget_totals[k]+=v
        return IncidentPulseGroup(signal,np.full(len(centers),o.wavelength_nm),centers,o.pulse_shape,o.pulse_fwhm_ps,tail)

"""B: full Tx angular footprint → Rx PSF → physical pixels → shared SPAD engine."""
from typing import Literal
from types import SimpleNamespace
from hashlib import sha256
import json
import numpy as np
from pydantic import Field, model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import SpectralInputs, Curve
from ..constants import C, H
from ..contracts import SensorIllumination
from ..tx import angular_profile, transmit
from ..scene import lambertian_return
from ..rx.budget import aperture_area
from ..rx.spatial import synthetic_receiver
from ..adapters.optical_data import validate_dataset, RxTable
from ..spectra import spectral_components
from ..spad.device import effective_pde
from .configuration import TimingConfig
from .lab import run_illumination, stamp_result


class OpticalConfig(StrictConfig):
    tx_model: Literal['gaussian','uniform','dataset']
    rx_model: Literal['gaussian_psf','uniform_pixel','dataset']
    dataset: dict | None
    channels_h: int = Field(ge=1,strict=True)
    channels_v: int = Field(ge=1,strict=True)
    pixel_pitch_um: float = Field(gt=0)
    focal_length_mm: float = Field(gt=0)
    tx_fwhm_h_mrad: float = Field(gt=0)
    tx_fwhm_v_mrad: float = Field(gt=0)
    tx_center_h_mrad: float
    tx_center_v_mrad: float
    psf_sigma_um: float = Field(gt=0)
    rx_offset_x_um: float
    rx_offset_y_um: float
    angle_h_min_mrad: float
    angle_h_max_mrad: float
    angle_v_min_mrad: float
    angle_v_max_mrad: float
    total_pulse_energy_nj: float = Field(ge=0)
    range_m: float = Field(gt=0)
    target_reflectivity: float = Field(ge=0,le=1)
    wavelength_nm: float = Field(gt=0)
    pulse_shape: Literal['gaussian','rectangular']
    pulse_fwhm_ps: float = Field(gt=0)
    tx_efficiency: float = Field(ge=0,le=1)
    atmospheric_one_way_transmission: float = Field(ge=0,le=1)
    overlap_factor: float = Field(ge=0,le=1)
    rx_efficiency: float = Field(ge=0,le=1)
    rx_aperture_shape: Literal['circle','ellipse','rectangle']
    rx_aperture_mm: float = Field(gt=0)
    rx_aperture_width_mm: float = Field(gt=0)
    rx_aperture_height_mm: float = Field(gt=0)
    solar_enabled: bool
    solar_illuminance_lux: float = Field(ge=0)
    solar_reflectivity: float = Field(ge=0,le=1)
    other_light_enabled: bool
    other_light_scale: float = Field(ge=0)
    calibration_delay_ns: float

    @model_validator(mode='after')
    def valid(self):
        if self.angle_h_max_mrad<=self.angle_h_min_mrad or self.angle_v_max_mrad<=self.angle_v_min_mrad:
            raise ValueError('Angular domain edges must be increasing')
        if (self.tx_model=='dataset' or self.rx_model=='dataset') and self.dataset is None:
            raise ValueError('Selected optical model requires an explicit dataset')
        return self


class SystemConfig(StrictConfig):
    device: DeviceConfig
    readout: ReadoutConfig
    timing: TimingConfig
    optics: OpticalConfig
    spectral_inputs: SpectralInputs
    rng_seed: int = Field(ge=0,strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.readout.readout_mode=='analytic_reference':
            raise ValueError('Spatial acquisition requires an event readout mode')
        if self.readout.readout_mode.startswith('coincidence') and self.readout.coincidence_threshold>self.device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds group size')
        if self.optics.pulse_fwhm_ps*1e-3>=self.timing.period_ns:
            raise ValueError('Pulse width must be shorter than period')
        return self


def system_defaults(base):
    return {'optics':{k:base[k] for k in OpticalConfig.model_fields if k in base},
            'spectral_inputs':base['spectral_inputs']}


def optical_dataset(cfg,a):
    o=cfg.optics
    imported=validate_dataset(o.dataset,a) if o.tx_model=='dataset' or o.rx_model=='dataset' else None
    if o.tx_model=='dataset':
        tx=imported.tx.model_dump()
    else:
        he,ve,f=angular_profile(o,a)
        tx={'reference_plane':'after_tx_optics','h_edges_mrad':he.tolist(),'v_edges_mrad':ve.tolist(),'energy_fraction':f.tolist()}
    if o.rx_model=='dataset':
        rx=imported.rx.model_dump()
    else:
        filt=Curve(cfg.spectral_inputs.filter)
        rx=synthetic_receiver(o,cfg.device,[filt.x[0],o.wavelength_nm,filt.x[-1]],a)
    # Metadata explicitly distinguishes generated models from imported measurements.
    synthetic=(o.tx_model!='dataset' or o.rx_model!='dataset' or imported.synthetic)
    doc={'schema_version':1,'coordinate_convention':'optical_H_right_V_down__image_x_right_y_down',
         'label':'构造光学样例 / Gaussian or uniform reference' if synthetic else imported.label,
         'synthetic':synthetic,'provenance':{'generator':'spad-spatial-v1','tx_model':o.tx_model,'rx_model':o.rx_model,
         'parameters':o.model_dump(exclude={'dataset'}),'algorithms':{k:getattr(a,k) for k in ('spatial_angle_samples_h','spatial_angle_samples_v')},
         'imported':imported.provenance if imported else None,
         'imported_label':imported.label if imported else None},'tx':tx,'rx':rx}
    data=validate_dataset(doc,a)
    nx=o.channels_h*cfg.device.H_binning;ny=o.channels_v*cfg.device.V_binning
    if len(data.rx.x_edges_um)!=nx+1 or len(data.rx.y_edges_um)!=ny+1:
        raise ValueError('Optical database pixel layout does not match channels × H/V binning')
    return data


def project_illumination(cfg,a,progress,cancelled):
    o=cfg.optics
    if max(abs(x) for x in (o.angle_h_min_mrad,o.angle_h_max_mrad,o.angle_v_min_mrad,o.angle_v_max_mrad))>a.max_spatial_angle_mrad:
        raise ValueError('Angular domain exceeds configured paraxial model range')
    dataset=optical_dataset(cfg,a)
    tx=dataset.tx
    he=np.array(tx.h_edges_mrad);ve=np.array(tx.v_edges_mrad)
    hh,vv=np.meshgrid((he[:-1]+he[1:])/2,(ve[:-1]+ve[1:])/2)
    fractions=np.asarray(tx.energy_fraction).ravel()
    omega=np.outer(np.diff(ve),np.diff(he)).ravel()*1e-6
    nx=o.channels_h*cfg.device.H_binning;ny=o.channels_v*cfg.device.V_binning
    yy,xx=np.indices((ny,nx))
    groups=((yy//cfg.device.V_binning)*o.channels_h+xx//cfg.device.H_binning).ravel()
    table=RxTable(dataset.rx)
    if len(fractions)*nx*ny>a.max_optical_cells:
        raise ValueError('Angle-to-pixel mapping exceeds max_optical_cells before allocation')
    eff,psf=table.evaluate(o.wavelength_nm,hh,vv)
    psf=psf.reshape(len(fractions),-1)
    area=aperture_area(o)
    total_j=o.total_pulse_energy_nj*1e-9
    emitted=transmit(total_j,o.tx_efficiency)
    target_incident,target_reflected,pupil,geometry=lambertian_return(emitted*fractions,o.atmospheric_one_way_transmission,
        o.target_reflectivity,area,o.range_m,o.overlap_factor)
    filt=Curve(cfg.spectral_inputs.filter)
    filter_at=float(filt(o.wavelength_nm))
    after_rx=pupil*eff
    after_filter=after_rx*filter_at
    pixel_j=after_filter@psf
    photon_j=H*C/(o.wavelength_nm*1e-9)
    signal_photons=pixel_j/photon_j
    proxy=SimpleNamespace(**o.model_dump(exclude={'dataset'}),spectral_inputs=cfg.spectral_inputs,fill_factor=cfg.device.fill_factor)
    spectral=spectral_components(proxy,a,plot=True)
    integration=spectral['integration']
    wavelengths=np.array(integration['wavelength_nm'])
    weights=np.array(integration['weights_nm'])
    transmission=np.array(integration['filter_transmission'])
    sun=np.array(integration['solar_radiance']);ambient=np.array(integration['other_radiance'])
    if len(wavelengths)*len(fractions)*nx*ny>a.max_spatial_integration_work:
        raise ValueError('Spatial/spectral integration exceeds configured work limit')
    if nx*ny*(len(wavelengths)+1)>a.max_optical_cells:
        raise ValueError('Detector spectral measures exceed configured array limit')
    solar=np.zeros((nx*ny,len(wavelengths)));other=np.zeros_like(solar)
    pupil_solar_rate=0.;pupil_other_rate=0.
    rx_solar_rate=0.;rx_other_rate=0.
    filter_solar_rate=0.;filter_other_rate=0.
    for j,(wl,weight,t,ls,lo) in enumerate(zip(wavelengths,weights,transmission,sun,ambient)):
        photon_factor=wl*1e-9/(H*C)
        sun_input=area*omega*ls*weight*photon_factor
        other_input=area*omega*lo*weight*photon_factor
        pupil_solar_rate+=sun_input.sum();pupil_other_rate+=other_input.sum()
        if ls!=0 or lo!=0:
            e,p=table.evaluate(wl,hh,vv)
            p=p.reshape(len(fractions),-1)
            rx_solar_rate+=(sun_input*e).sum();rx_other_rate+=(other_input*e).sum()
            filter_solar_rate+=(sun_input*e*t).sum();filter_other_rate+=(other_input*e*t).sum()
            solar[:,j]=(sun_input*e*t)@p
            other[:,j]=(other_input*e*t)@p
        if (j+1)%a.spatial_wavelength_chunk_size==0 or j+1==len(wavelengths):
            progress(j+1,len(wavelengths),'空间与光谱积分')
            if cancelled():
                raise InterruptedError('Cancelled during optical projection')
    wl_all=np.r_[o.wavelength_nm,wavelengths]
    signal=np.zeros((nx*ny,len(wl_all)));signal[:,0]=signal_photons
    background=np.column_stack((np.zeros(nx*ny),solar+other))
    light=SensorIllumination(wl_all,signal,background,o.pulse_shape,o.pulse_fwhm_ps,2*o.range_m/C*1e9+o.calibration_delay_ns,
        {'kind':'spatial_optical_projection','reference_plane':'full_pixel_before_PDE_FF','dataset_label':dataset.label,'synthetic':dataset.synthetic})
    capture=psf.sum(axis=1)
    gate_s=cfg.timing.gate_width_ns*1e-9
    pde=Curve(cfg.spectral_inputs.pde)
    detector_response=effective_pde(pde(wavelengths),cfg.device.fill_factor)
    budget={
        'tx_input_j':total_j,'tx_output_j':emitted,'tx_angular_coverage_fraction':float(fractions.sum()),
        'tx_angular_truncation_j':float(emitted*(1-fractions.sum())),
        'target_incident_j':float(target_incident.sum()),'target_reflected_j':float(target_reflected.sum()),
        'rx_pupil_signal_j':float(pupil.sum()),'after_rx_signal_j':float(after_rx.sum()),
        'after_filter_fullplane_signal_j':float(after_filter.sum()),'sensor_signal_j':float(pixel_j.sum()),
        'rx_loss_j':float(pupil.sum()-after_rx.sum()),'filter_loss_j':float(after_rx.sum()-after_filter.sum()),
        'psf_edge_loss_j':float(after_filter.sum()-pixel_j.sum()),
        'signal_rx_incident_photons_per_pulse':float(pupil.sum()/photon_j),
        'signal_sensor_incident_photons_per_pulse':float(signal_photons.sum()),
        'signal_candidate_avalanches_per_pulse':float(signal_photons.sum()*effective_pde(pde(o.wavelength_nm),cfg.device.fill_factor)),
        'solar_rx_incident_photons_per_gate':float(pupil_solar_rate*gate_s),
        'other_rx_incident_photons_per_gate':float(pupil_other_rate*gate_s),
        'solar_after_rx_photons_per_gate':float(rx_solar_rate*gate_s),'other_after_rx_photons_per_gate':float(rx_other_rate*gate_s),
        'solar_after_filter_fullplane_photons_per_gate':float(filter_solar_rate*gate_s),
        'other_after_filter_fullplane_photons_per_gate':float(filter_other_rate*gate_s),
        'solar_sensor_incident_photons_per_gate':float(solar.sum()*gate_s),
        'other_sensor_incident_photons_per_gate':float(other.sum()*gate_s),
        'solar_candidate_avalanches_per_gate':float((solar@detector_response).sum()*gate_s),
        'other_candidate_avalanches_per_gate':float((other@detector_response).sum()*gate_s),
        'aperture_area_m2':area,'angular_solid_angle_sr':float(omega.sum()),
        'background_integration_band_nm':spectral['budget_band_nm'],
        'energy_balance_residual_j':float(pupil.sum()-(pixel_j.sum()+(pupil.sum()-after_rx.sum())+(after_rx.sum()-after_filter.sum())+(after_filter.sum()-pixel_j.sum()))),
    }
    mapping=np.zeros((len(fractions),o.channels_h*o.channels_v))
    for channel in range(mapping.shape[1]):
        mapping[:,channel]=psf[:,groups==channel].sum(axis=1)
    checksum=sha256(json.dumps(dataset.model_dump(),sort_keys=True,allow_nan=False).encode()).hexdigest()
    info={'budget':budget,'dataset':dataset.model_dump(),'dataset_sha256':checksum,
          'array_shape':[ny,nx],'channel_shape':[o.channels_v,o.channels_h],
          'angular_h_centers_mrad':hh.ravel().tolist(),'angular_v_centers_mrad':vv.ravel().tolist(),
          'pixel_group_ids':groups.tolist(),'tx_h_edges_mrad':he.tolist(),'tx_v_edges_mrad':ve.tolist(),
          'tx_energy_fraction':np.asarray(tx.energy_fraction).tolist(),
          'angle_to_channel_fraction':mapping.tolist(),'psf_capture_fraction':capture.reshape(hh.shape).tolist(),
          'signal_energy_per_pixel_j':pixel_j.reshape(ny,nx).tolist(),
          'solar_photons_per_pixel_per_gate':(solar.sum(axis=1)*gate_s).reshape(ny,nx).tolist(),
          'other_photons_per_pixel_per_gate':(other.sum(axis=1)*gate_s).reshape(ny,nx).tolist(),
          'spectral_integration':{'wavelength_nm':wavelengths.tolist(),'weights_nm':weights.tolist(),
                                  'filter_transmission':transmission.tolist(),'solar_radiance_w_m2_sr_nm':sun.tolist(),
                                  'other_radiance_w_m2_sr_nm':ambient.tolist(),
                                  'solar_sensor_photons_per_second_per_spectral_cell':solar.tolist(),
                                  'other_sensor_photons_per_second_per_spectral_cell':other.tolist()},
          'assumptions':['Static extended Lambertian target with one range and reflectivity.',
                         'Small-angle solid angle dH*dV in radians; configured angular validity limit enforced.',
                         'Synthetic Rx is an achromatic Gaussian PSF or an explicitly uniform reference.',
                         'PSF fractions refer to full pixels before PDE/FF; no edge renormalization.',
                         'FF is an effective within-pixel factor; active-area microgeometry is not resolved.',
                         'No scanning, afterpulse, avalanche crosstalk or shared resources between output groups.']}
    return light,groups,info


def run_system(cfg,a,progress,cancelled):
    light,groups,optics=project_illumination(cfg,a,progress,cancelled)
    result=run_illumination(cfg,a,light,groups,progress,cancelled)
    result['illumination']={'signal_photons_per_pixel_per_pulse':light.signal_photons_per_pulse.sum(axis=1).tolist(),
                            'background_photons_per_pixel_per_second':light.background_photons_per_second.sum(axis=1).tolist(),
                            'shape':optics['array_shape'],'provenance':light.provenance}
    result['optics']=optics
    result['provenance_extra']={'optical_dataset_sha256':optics['dataset_sha256']}
    from ..reporting.spatial_flow import build_spatial_flow
    result['photon_flow']=build_spatial_flow(optics['budget'],result['audit'])
    from ..processing.spatial_ranges import estimate_channels
    result['channel_ranges']=estimate_channels(cfg,a,result['histogram'])
    return stamp_result('B_full_spot_static',cfg,a,result)

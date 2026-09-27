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
from ..tx import angular_profile, transmit, normalize_angular_weights
from ..scene import lambertian_return
from ..rx.budget import aperture_area
from ..rx.spatial import synthetic_receiver
from ..rx.response import ReceiverResponse
from ..rx.projection import project_return
from ..adapters.optical_data import validate_dataset, RxTable
from ..spectra import spectral_components, background_spectral_domain
from ..contracts.spectral_product import SpectralProduct,export_spectral
from ..spad.device import effective_pde
from .configuration import TimingConfig
from .lab import run_illumination, stamp_result


class OpticalConfig(StrictConfig):
    tx_model: Literal['gaussian','super_gaussian','uniform','dataset']
    rx_model: Literal['gaussian_psf','super_gaussian_psf','uniform_pixel','dataset']
    dataset: dict | None
    channels_h: int = Field(ge=1,strict=True)
    channels_v: int = Field(ge=1,strict=True)
    pixel_pitch_um: float = Field(gt=0)
    focal_length_h_mm: float = Field(gt=0)
    focal_length_v_mm: float = Field(gt=0)
    mapping_mode: Literal['inverted','legacy_upright']
    tx_fwhm_h_mrad: float = Field(gt=0)
    tx_fwhm_v_mrad: float = Field(gt=0)
    tx_center_h_mrad: float
    tx_center_v_mrad: float
    tx_order_h: float = Field(ge=1)
    tx_order_v: float = Field(ge=1)
    psf_sigma_h_um: float = Field(gt=0)
    psf_sigma_v_um: float = Field(gt=0)
    psf_order_h: float = Field(ge=1)
    psf_order_v: float = Field(ge=1)
    rx_offset_x_um: float
    rx_offset_y_um: float
    angle_h_min_mrad: float
    angle_h_max_mrad: float
    angle_v_min_mrad: float
    angle_v_max_mrad: float
    rx_angle_h_min_mrad: float
    rx_angle_h_max_mrad: float
    rx_angle_v_min_mrad: float
    rx_angle_v_max_mrad: float
    pulse_average_power_w: float = Field(ge=0)
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

    @property
    def total_pulse_energy_nj(self):
        from ..tx.power import pulse_energy_nj
        return pulse_energy_nj(self.pulse_average_power_w,self.pulse_fwhm_ps)

    @model_validator(mode='after')
    def valid(self):
        if self.angle_h_max_mrad<=self.angle_h_min_mrad or self.angle_v_max_mrad<=self.angle_v_min_mrad:
            raise ValueError('Angular domain edges must be increasing')
        if self.rx_angle_h_max_mrad<=self.rx_angle_h_min_mrad or self.rx_angle_v_max_mrad<=self.rx_angle_v_min_mrad:
            raise ValueError('Receiver angular coverage edges must increase')
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
    from ..numerics.spatial_profiles import validate_profile_orders
    validate_profile_orders(o,a)
    imported=validate_dataset(o.dataset,a) if o.tx_model=='dataset' or o.rx_model=='dataset' else None
    if o.tx_model=='dataset':
        tx=imported.tx.model_dump()
        input_sum=float(np.asarray(tx['energy_fraction']).sum())
        tx['energy_fraction']=normalize_angular_weights(tx['energy_fraction']).tolist()
    else:
        he,ve,f=angular_profile(o,a)
        input_sum=1.  # The generated profile already represents the conditional domain distribution.
        tx={'reference_plane':'after_tx_optics','h_edges_mrad':he.tolist(),'v_edges_mrad':ve.tolist(),'energy_fraction':f.tolist()}
    normalization={'mode':'within_configured_angular_domain',
        'energy_reference':'configured_domain_before_tx_optics',
        'source':'imported_fractions' if o.tx_model=='dataset' else 'generated_conditional_profile',
        'input_fraction_sum':input_sum,'normalized_fraction_sum':float(np.asarray(tx['energy_fraction']).sum()),
        'note':'Pulse energy is defined inside these Tx angular edges; no angular truncation energy is deducted. Rx PSF and temporal gate losses remain separate.'}
    if o.rx_model=='dataset':
        rx=imported.rx.model_dump()
    else:
        filt=Curve(cfg.spectral_inputs.filter)
        domain=background_spectral_domain(SimpleNamespace(**o.model_dump(exclude={'dataset'}),dataset=o.dataset,spectral_inputs=cfg.spectral_inputs),a)
        band=domain['band_nm']
        rx=synthetic_receiver(o,cfg.device,[band[0],o.wavelength_nm,band[-1]],a)
    # Metadata explicitly distinguishes generated models from imported measurements.
    synthetic=(o.tx_model!='dataset' or o.rx_model!='dataset' or imported.synthetic)
    doc={'schema_version':2,'coordinate_convention':'optical_H_right_V_up__image_x_right_y_up',
         'label':'构造光学样例 / Gaussian, super-Gaussian or uniform reference' if synthetic else imported.label,
         'synthetic':synthetic,'provenance':{'generator':'spad-spatial-v1','tx_model':o.tx_model,'rx_model':o.rx_model,
         'parameters':o.model_dump(exclude={'dataset'}),'tx_energy_normalization':normalization,
         'algorithms':{k:getattr(a,k) for k in ('spatial_angle_samples_h','spatial_angle_samples_v','rx_angle_samples_h','rx_angle_samples_v')},
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
    # Tx cells normalize signal energy only. Background has its own Rx grid.
    if a.background_angular_domain=='legacy_tx':
        rhe,rve=he,ve
    else:
        rhe=np.linspace(o.rx_angle_h_min_mrad,o.rx_angle_h_max_mrad,a.spatial_angle_samples_h+1)
        rve=np.linspace(o.rx_angle_v_min_mrad,o.rx_angle_v_max_mrad,a.spatial_angle_samples_v+1)
    rhh,rvv=np.meshgrid((rhe[:-1]+rhe[1:])/2,(rve[:-1]+rve[1:])/2)
    omega=np.outer(np.diff(rve),np.diff(rhe)).ravel()*1e-6
    nx=o.channels_h*cfg.device.H_binning;ny=o.channels_v*cfg.device.V_binning
    yy,xx=np.indices((ny,nx))
    groups=((yy//cfg.device.V_binning)*o.channels_h+xx//cfg.device.H_binning).ravel()
    table=ReceiverResponse(dataset.rx,o,a)
    if max(len(fractions),len(omega))*nx*ny>a.max_optical_cells:
        raise ValueError('Angle-to-pixel mapping exceeds max_optical_cells before allocation')
    eff,psf=table.evaluate(o.wavelength_nm,hh,vv)
    psf=psf.reshape(len(fractions),-1)
    area=aperture_area(o)
    total_j=o.total_pulse_energy_nj*1e-9
    emitted=transmit(total_j,o.tx_efficiency)
    filt=Curve(cfg.spectral_inputs.filter)
    filter_at=float(filt(o.wavelength_nm))
    projection=project_return(emitted*fractions,o.atmospheric_one_way_transmission,o.target_reflectivity,
                              area,o.range_m,o.overlap_factor,eff,filter_at,psf)
    target_incident,target_reflected,pupil,geometry=projection.target_incident,projection.target_reflected,projection.pupil,projection.geometry
    after_rx,after_filter,pixel_j=projection.after_rx,projection.after_filter,projection.pixel_energy
    photon_j=H*C/(o.wavelength_nm*1e-9)
    signal_photons=pixel_j/photon_j
    proxy=SimpleNamespace(**o.model_dump(exclude={'dataset'}),dataset=o.dataset,spectral_inputs=cfg.spectral_inputs,fill_factor=cfg.device.fill_factor)
    spectral=spectral_components(proxy,a,plot=True)
    integration=spectral['integration']
    wavelengths=np.array(integration['wavelength_nm'])
    weights=np.array(integration['weights_nm'])
    transmission=np.array(integration['filter_transmission'])
    sun=np.array(integration['solar_radiance']);ambient=np.array(integration['other_radiance'])
    factorized=a.factorize_achromatic_leakage and filt.has_out_of_band and o.rx_model!='dataset'
    work=(len(omega)*nx*ny+len(wavelengths)) if factorized else len(wavelengths)*len(omega)*nx*ny
    if work>a.max_spatial_integration_work:
        raise ValueError('Spatial/spectral integration exceeds configured work limit')
    stored_cells=nx*ny+len(wavelengths)+1 if factorized else nx*ny*(len(wavelengths)+1)
    if stored_cells>a.max_optical_cells:
        raise ValueError('Detector spectral measures exceed configured array limit')
    if factorized:
        # Generated Rx is explicitly achromatic. Separate exactly, without
        # coarsening the wavelength quadrature or dropping zero-PDE photons.
        q=weights*wavelengths*1e-9/(H*C)
        sun_spectral=sun*q;other_spectral=ambient*q
        bg_eff,bg_psf=table.evaluate(o.wavelength_nm,rhh,rvv)
        bg_psf=bg_psf.reshape(len(omega),-1)
        pupil_factor=area*omega.sum();rx_factor=area*np.dot(omega,bg_eff)
        pixel_factor=area*((omega*bg_eff)@bg_psf)
        pupil_solar_rate=pupil_factor*sun_spectral.sum();pupil_other_rate=pupil_factor*other_spectral.sum()
        rx_solar_rate=rx_factor*sun_spectral.sum();rx_other_rate=rx_factor*other_spectral.sum()
        filter_solar_rate=rx_factor*np.dot(sun_spectral,transmission);filter_other_rate=rx_factor*np.dot(other_spectral,transmission)
        solar=SpectralProduct(pixel_factor,sun_spectral*transmission)
        other=SpectralProduct(pixel_factor,other_spectral*transmission)
        progress(len(wavelengths),len(wavelengths),'无色差Rx：精确分离空间与全波段积分')
        if cancelled():raise InterruptedError('Cancelled during optical projection')
    else:
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
                e,p=table.evaluate(wl,rhh,rvv)
                p=p.reshape(len(omega),-1)
                rx_solar_rate+=(sun_input*e).sum();rx_other_rate+=(other_input*e).sum()
                filter_solar_rate+=(sun_input*e*t).sum();filter_other_rate+=(other_input*e*t).sum()
                solar[:,j]=(sun_input*e*t)@p
                other[:,j]=(other_input*e*t)@p
            if (j+1)%a.spatial_wavelength_chunk_size==0 or j+1==len(wavelengths):
                progress(j+1,len(wavelengths),'空间与光谱积分')
                if cancelled():raise InterruptedError('Cancelled during optical projection')
    wl_all=np.r_[o.wavelength_nm,wavelengths]
    if factorized:
        signal=SpectralProduct(signal_photons,np.r_[1.,np.zeros_like(wavelengths)])
        background=SpectralProduct(pixel_factor,np.r_[0.,solar.spectral+other.spectral])
    else:
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
        'tx_domain_output_j':emitted,
        'tx_angular_truncation_j':0.,  # Legacy export key: domain-defined energy has no angular truncation loss.
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
        'solar_candidate_rate_cps':float((solar@detector_response).sum()),
        'other_candidate_rate_cps':float((other@detector_response).sum()),
        'aperture_area_m2':area,'angular_solid_angle_sr':float(omega.sum()),
        'background_integration_band_nm':spectral['budget_band_nm'],
        'background_integration_domain':spectral['integration_domain'],
        'background_angular_domain':{'mode':a.background_angular_domain,
            'h_edges_mrad':rhe.tolist(),'v_edges_mrad':rve.tolist(),
            'solid_angle_sr':float(omega.sum())},
        'energy_balance_residual_j':float(pupil.sum()-(pixel_j.sum()+(pupil.sum()-after_rx.sum())+(after_rx.sum()-after_filter.sum())+(after_filter.sum()-pixel_j.sum()))),
    }
    from ..reporting.background_bins import spatial_background_bin_values
    budget.update(spatial_background_bin_values(budget,cfg.readout.tdc_bin_ps))
    mapping=np.zeros((len(fractions),o.channels_h*o.channels_v))
    for channel in range(mapping.shape[1]):
        mapping[:,channel]=psf[:,groups==channel].sum(axis=1)
    checksum=sha256(json.dumps(dataset.model_dump(),sort_keys=True,allow_nan=False).encode()).hexdigest()
    info={'budget':budget,'dataset':dataset.model_dump(),'dataset_sha256':checksum,
          'tx_energy_normalization':dataset.provenance['tx_energy_normalization'],
          'array_shape':[ny,nx],'channel_shape':[o.channels_v,o.channels_h],
          'angular_h_centers_mrad':hh.ravel().tolist(),'angular_v_centers_mrad':vv.ravel().tolist(),
          'pixel_group_ids':groups.tolist(),'tx_h_edges_mrad':he.tolist(),'tx_v_edges_mrad':ve.tolist(),
          'tx_energy_fraction':np.asarray(tx.energy_fraction).tolist(),
          'rx_background_h_edges_mrad':rhe.tolist(),'rx_background_v_edges_mrad':rve.tolist(),
          'angle_to_channel_fraction':mapping.tolist(),'psf_capture_fraction':capture.reshape(hh.shape).tolist(),
          'signal_energy_per_pixel_j':pixel_j.reshape(ny,nx).tolist(),
          'solar_photons_per_pixel_per_gate':(solar.sum(axis=1)*gate_s).reshape(ny,nx).tolist(),
          'other_photons_per_pixel_per_gate':(other.sum(axis=1)*gate_s).reshape(ny,nx).tolist(),
          'spectral_integration':{'storage':'outer_product' if factorized else 'dense',
                                  'domain':spectral['integration_domain'],'integration_work':work,
                                  'logical_cells':nx*ny*len(wavelengths),'stored_cells_per_measure':stored_cells,
                                  'wavelength_nm':wavelengths.tolist(),'weights_nm':weights.tolist(),
                                  'filter_transmission':transmission.tolist(),'solar_radiance_w_m2_sr_nm':sun.tolist(),
                                  'other_radiance_w_m2_sr_nm':ambient.tolist(),
                                  'solar_sensor_photons_per_second_per_spectral_cell':export_spectral(solar),
                                  'other_sensor_photons_per_second_per_spectral_cell':export_spectral(other)},
          'assumptions':['Tx pulse energy is defined within the configured angular domain before Tx efficiency; cell fractions sum to unity.',
                         'Static extended Lambertian target with one range and reflectivity.',
                         'Small-angle solid angle dH*dV in radians; configured angular validity limit enforced.',
                         'Synthetic Rx uses separable achromatic Gaussian/super-Gaussian PSFs with true H/V standard deviations, or a uniform pixel reference.',
                         'PSF fractions refer to full pixels before PDE/FF; no edge renormalization.',
                         'FF is an effective within-pixel factor; active-area microgeometry is not resolved.',
                         'No scanning, afterpulse, avalanche crosstalk or shared resources between output groups.']}
    return light,groups,info


def system_program(cfg,a):
    from ..timing import periodic_program
    t=cfg.timing
    first=0 if a.b_initial_condition=='fully_recovered' else -a.readout_warmup_cycles
    return periodic_program(t.period_ns,t.gate_start_ns,t.gate_width_ns,first,t.laser_shots,t.laser_shots)


def run_system(cfg,a,progress,cancelled):
    light,groups,optics=project_illumination(cfg,a,progress,cancelled)
    result=run_illumination(cfg,a,light,groups,progress,cancelled,program=system_program(cfg,a))
    return finish_system(cfg,a,result,light,groups,optics)


def finish_system(cfg,a,result,light,groups,optics):
    result['audit']['initialization']={'mode':a.b_initial_condition,
        'warmup_cycles':0 if a.b_initial_condition=='fully_recovered' else a.readout_warmup_cycles,
        'scope':'This independent static acquisition only; not a C inter-column reset implementation.'}
    result['illumination']={'signal_photons_per_pixel_per_pulse':light.signal_photons_per_pulse.sum(axis=1).tolist(),
                            'background_photons_per_pixel_per_second':light.background_photons_per_second.sum(axis=1).tolist(),
                            'shape':optics['array_shape'],'provenance':light.provenance}
    result['optics']=optics
    result['provenance_extra']={'optical_dataset_sha256':optics['dataset_sha256']}
    from ..reporting.spatial_flow import build_spatial_flow
    result['photon_flow']=build_spatial_flow(optics['budget'],result['audit'])
    from ..processing.spatial_ranges import estimate_channels
    result['channel_ranges']=estimate_channels(cfg,a,result['histogram'])
    stamped=stamp_result('B_full_spot_static',cfg,a,result)
    if a.b_initial_condition=='fully_recovered':
        stamped['provenance']['limitations']=[s for s in stamped['provenance']['limitations'] if s!='Finite warmup, step recovery.']
        stamped['provenance']['limitations'].append('Independent B acquisition starts fully recovered, without prehistory; step recovery within the acquisition.')
    return stamped

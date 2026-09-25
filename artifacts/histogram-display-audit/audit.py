"""Read-only peak audit plus one same-candidate, zero-deadtime counterfactual."""
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import sys,json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.configuration import Algorithms,frozen_yaml
from spad_lidar.experiments.system_config import BSystemConfig
from spad_lidar.experiments.spatial import system_program
from spad_lidar.experiments.lab import acquire_candidates
from spad_lidar.spad.source import sample_candidates
from spad_lidar.spad.acquisition import evolve_program
from spad_lidar.spad.device.state import DeviceState
from spad_lidar.contracts import SensorIllumination
from spad_lidar.curves import Curve
from spad_lidar.constants import C,H
from spad_lidar.reporting.b_acquisition import histogram_scope_view

JOB='07814a948d114a18bcda2d666b84ca10'
OUT=Path(__file__).parent
path=ROOT/'artifacts/runs'/JOB/'result.json'
saved=json.loads(path.read_text(encoding='utf-8'))
request=json.loads(path.with_name('request.json').read_text(encoding='utf-8'))
noop=lambda *args:None
never=lambda:False

with frozen_yaml(request['yaml']):
    cfg=BSystemConfig.model_validate(saved['configuration']['experiment'])
    a=Algorithms.model_validate(saved['configuration']['algorithms'])
    optics=saved['optics'];s=optics['spectral_integration'];groups=np.array(optics['pixel_group_ids'])
    wavelengths=np.r_[cfg.tx.wavelength_nm,s['wavelength_nm']]
    signal=np.zeros((len(groups),len(wavelengths)))
    signal[:,0]=np.array(optics['signal_energy_per_pixel_j']).ravel()/(H*C/(cfg.tx.wavelength_nm*1e-9))
    bg=np.column_stack((np.zeros(len(groups)),np.array(s['solar_sensor_photons_per_second_per_spectral_cell'])+np.array(s['other_sensor_photons_per_second_per_spectral_cell'])))
    light=SensorIllumination(wavelengths,signal,bg,cfg.tx.pulse_shape,cfg.tx.pulse_fwhm_ps,
        2*cfg.scene.range_m/C*1e9+cfg.acquisition.calibration_delay_ns,{'source_job':JOB})
    program=system_program(cfg,a);streams=np.random.SeedSequence(cfg.rng_seed).spawn(2)
    candidates,source=sample_candidates(light,cfg.device,Curve(cfg.spectral_inputs.pde),program,np.random.default_rng(streams[0]),a.max_readout_events_per_run)
    first=acquire_candidates(cfg,a,candidates,source,groups,program,streams[1],noop,never)
    assert first['records']==saved['records']
    values=cfg.model_dump();values['spad']['spad_dead_time_ns']=0
    zero_cfg=BSystemConfig.model_validate(values)
    zero=acquire_candidates(zero_cfg,a,candidates,source,groups,program,streams[1],noop,never)
    edges=np.array(saved['histogram']['edges_ns']);ch=4
    times=np.array(saved['histogram']['time_ns'])
    ref=saved['references'][ch];peak_bin=int(np.argmax(ref['counts']))

    class TracedDevice(DeviceState):
        def __init__(self,n):
            super().__init__(n);self.events=[]
        def avalanche(self,t,pixel,dead_time_ns):
            accepted=super().avalanche(t,pixel,dead_time_ns)
            self.events.append((float(t),int(pixel),accepted))
            return accepted

    device=TracedDevice(len(groups))
    session=evolve_program(cfg.device,cfg.readout,groups,program,candidates,a,noop,never,device_engine=device)
    assert session.stats['spad_dead_losses']==saved['audit']['spad_dead_losses']
    channel_events=[e for e in device.events if groups[e[1]]==ch]
    peak_events=[e for e in channel_events if edges[peak_bin] <= e[0]%cfg.timing.period_ns < edges[peak_bin+1]]
    loss={'channel_candidate_events':len(channel_events),'channel_deadtime_rejected':sum(not e[2] for e in channel_events),
        'candidate_events_in_ideal_peak_bin':len(peak_events),'accepted_avalanches_in_ideal_peak_bin':sum(e[2] for e in peak_events),
        'deadtime_rejected_in_ideal_peak_bin':sum(not e[2] for e in peak_events),
        'note':'Counts at pre-electronic-jitter avalanche times; mixed signal and background are not source-labelled.'}
    views={}
    for scope in ('slot','gate'):
        view=histogram_scope_view(saved,cfg,a,scope,2,cfg.readout.tdc_bin_ps,[ch])
        r=view['references'][ch];counts=view['histogram']['counts'][ch]
        views[scope]={'shots':view['shots_in_view'],'gate_index':view['gate_index'],
            'ideal_signal_total':r['full_signal_total'],'ideal_continuous_peak':max(r['high_resolution']['counts_per_nominal_bin']),
            'ideal_binned_peak':max(r['counts']),'observed_peak':max(counts),
            'observed_peak_time_ns':float(times[np.argmax(counts)]),
            'ideal_noise_per_bin':view['noise_reference']['counts_per_bin'][ch]}
    np.testing.assert_allclose(views['slot']['ideal_continuous_peak']/cfg.timing.laser_shots,views['gate']['ideal_continuous_peak'])
    zero_counts=zero['histogram']['counts'][ch]
    counterfactual={'spad_dead_time_ns':0,'observed_slot_peak':max(zero_counts),
        'counts_in_original_ideal_peak_bin':zero_counts[peak_bin],
        'all_array_audit':{k:v for k,v in zero['audit'].items() if k not in ('trace','source')},
        'note':'Exactly the same sampled candidates and electronic seed; changing accepted events changes electronic jitter draws per record.'}
    report={'utc':datetime.now(timezone.utc).isoformat(),'job':JOB,'result_sha256':sha256(path.read_bytes()).hexdigest(),
        'configuration':saved['configuration'],'provenance':saved['provenance'],
        'channel':ch,'reference_peak_bin_edges_ns':edges[peak_bin:peak_bin+2].tolist(),
        'views':views,'per_gate_peaks':[max(histogram_scope_view(saved,cfg,a,'gate',i,cfg.readout.tdc_bin_ps,[ch])['histogram']['counts'][ch]) for i in range(cfg.timing.laser_shots)],
        'traced_losses':loss,'zero_deadtime_counterfactual':counterfactual,
        'checks':{'original_records_reproduced_exactly':True,'slot_and_single_gate_reference_scale_correct':True,'same_candidates_used_for_deadtime_control':True},
        'limitations':['The ideal line is pure signal before SPAD deadtime/readout, not the expected recorded mixed output.',
            'Continuous density times nominal bin width and integrated-bin dots have different peaks.',
            'One counterfactual demonstrates the mechanism but does not estimate a statistical detection SNR.']}
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    np.savez_compressed(OUT/'diagnostic-arrays.npz',edges_ns=edges,original=np.asarray(saved['histogram']['counts']),zero_deadtime=np.asarray(zero['histogram']['counts']),
        candidates_time_ns=candidates.time_ns,candidates_pixel_id=candidates.pixel_id,device_trace=np.array(device.events))
    print(json.dumps({k:report[k] for k in ('views','per_gate_peaks','traced_losses','zero_deadtime_counterfactual','checks')},ensure_ascii=False,indent=2))

"""Repeatable B analysis assembled from the same acquisition and temporal cores."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
from .spatial import project_illumination, finish_system, system_program
from .lab import run_illumination
from .system_config import BSystemConfig
from ..curves import Curve
from ..spad.device import effective_pde
from ..processing.statistics import histogram_sample_range
from ..reporting.a_view import signal_ground_truth
from ..reporting.spatial_view import optical_view


def with_seed(cfg,seed):
    values=cfg.model_dump()
    values['acquisition']['rng_seed']=seed
    return BSystemConfig.model_validate(values)


def channel_references(cfg,a,light,groups,edges,bin_ps):
    channels=int(groups.max())+1
    factor=min(a.histogram_preview_subdivisions,a.max_histogram_preview_bins//(len(edges)-1))
    if channels*((len(edges)-1)*factor+a.ground_truth_plot_points)>a.max_lab_reference_cells:
        raise ValueError('Analytical reference arrays exceed max_lab_reference_cells')
    response=effective_pde(Curve(cfg.spectral_inputs.pde)(light.wavelength_nm),cfg.device.fill_factor)
    incident=light.signal_photons_per_pulse.sum(axis=1)
    candidates=light.signal_photons_per_pulse@response
    parameters={**cfg.optics.model_dump(exclude={'dataset'}),**cfg.device.model_dump(),
                **cfg.readout.model_dump(),**cfg.timing.model_dump(),'tdc_bin_ps':bin_ps}
    proxy=SimpleNamespace(**parameters)
    references=[]
    for channel in range(channels):
        budget=SimpleNamespace(signal_detected_per_pulse=float(candidates[groups==channel].sum()),
                               signal_sensor_incident_photons_per_pulse=float(incident[groups==channel].sum()))
        references.append(signal_ground_truth(proxy,budget,np.asarray(edges),a))
    return references


def run_system_analysis(cfg,a,progress,cancelled):
    repeats=cfg.acquisition.monte_carlo_trials
    actual=max(1,repeats)
    noise_trials=a.readout_expected_trials if a.b_noise_reference=='sampled_output_mean' else 0
    channels=cfg.spad.channels_h*cfg.spad.channels_v
    bins=int(np.ceil(cfg.timing.gate_width_ns*1000/cfg.readout.tdc_bin_ps))
    if (actual+noise_trials)*channels*bins>a.max_lab_analysis_histogram_cells:
        raise ValueError('Repeated histogram arrays exceed max_lab_analysis_histogram_cells')
    light,groups,optics=project_illumination(cfg,a,progress,cancelled)
    total=actual+noise_trials
    program=system_program(cfg,a)
    def acquire(c,source,index,label):
        if cancelled():raise InterruptedError('Cancelled between repeated acquisitions')
        progress(index,total,label)
        return run_illumination(c,a,source,groups,lambda done,count,_:progress(index+done/count,total,label),cancelled,program=program)
    first=acquire(cfg,light,0,'首次采集')
    expected=first['audit']['source']['expected_work']*total
    if expected>a.max_lab_analysis_events:
        raise ValueError('Estimated repeated acquisition work exceeds max_lab_analysis_events')
    trials=[first['histogram']['counts']] if repeats else []
    trial_seeds=[cfg.rng_seed] if repeats else []
    streams=a.lab_analysis_seed_streams
    seeds=np.random.SeedSequence(cfg.rng_seed,spawn_key=(streams['trials'],)).spawn(max(0,repeats-1))
    for i,sequence in enumerate(seeds,1):
        seed=int(sequence.generate_state(1)[0]);out=acquire(with_seed(cfg,seed),light,i,'重复采集与误差棒')
        trials.append(out['histogram']['counts']);trial_seeds.append(seed)
    noise_source=replace(light,signal_photons_per_pulse=np.zeros_like(light.signal_photons_per_pulse))
    noise=[];noise_seeds=[]
    sequences=np.random.SeedSequence(cfg.rng_seed,spawn_key=(streams['noise'],)).spawn(noise_trials)
    for i,sequence in enumerate(sequences):
        seed=int(sequence.generate_state(1)[0]);out=acquire(with_seed(cfg,seed),noise_source,actual+i,'纯噪声期望')
        noise.append(out['histogram']['counts']);noise_seeds.append(seed)
    result=finish_system(cfg,a,first,light,groups,optics)
    bounds=histogram_sample_range(trials)
    result['statistics']={'trial_count':repeats,'noise_trial_count':noise_trials,
        'lower':bounds['lower_counts'],'upper':bounds['upper_counts'],'noise_mean':np.mean(noise,axis=0).tolist() if noise else None,
        'trial_histograms':trials,'noise_histograms':noise,'trial_seeds':trial_seeds,'noise_seeds':noise_seeds,
        'method':bounds['method'],'note':bounds['note'],'estimated_event_work':expected,
        'noise_reference_mode':a.b_noise_reference,
        'sampling_protocol':'B-analysis-role-separated-v1; first observation retains original acquisition seed'}
    if a.b_noise_reference=='candidate_scalar':
        from ..reporting.noise_reference import candidate_noise_reference
        result['noise_reference']=candidate_noise_reference(first['audit']['source'],groups,cfg.timing.laser_shots,cfg.timing.gate_width_ns,cfg.readout.tdc_bin_ps)
    result['references']=channel_references(cfg,a,light,groups,result['histogram']['edges_ns'],cfg.readout.tdc_bin_ps)
    result.update(optical_view(cfg,a,optics))
    progress(total,total,'统计完成')
    return result


def replay_analysis(result,cfg,a,bin_ps):
    """Rebin saved observations and every repeat before recomputing extrema."""
    from ..processing.records import histogram_records
    original=result['record_schema']['tdc_bin_ps'];factor=bin_ps/original
    if not np.isfinite(factor) or factor<1 or not np.isclose(factor,round(factor),rtol=0,atol=np.finfo(float).eps*max(1,factor)):
        raise ValueError('Replay bin must be an integer multiple of acquisition resolution')
    factor=round(factor)
    histogram=histogram_records(result['records'],cfg.timing.gate_start_ns,cfg.timing.gate_width_ns,bin_ps,len(result['histogram']['counts']))
    stats=result['statistics']
    def rebin(values):
        array=np.asarray(values)
        if not len(array):return []
        return np.add.reduceat(array,np.arange(0,array.shape[-1],factor),axis=-1).tolist()
    trials=rebin(stats['trial_histograms']);noise=rebin(stats['noise_histograms']);bounds=histogram_sample_range(trials)
    # Optical output is retained; reprojecting is unnecessary for digital rebinning.
    oldrefs=result['references'];edges=np.asarray(histogram['edges_ns'])
    proxy=SimpleNamespace(**{**cfg.optics.model_dump(exclude={'dataset'}),**cfg.device.model_dump(),**cfg.readout.model_dump(),**cfg.timing.model_dump(),'tdc_bin_ps':bin_ps})
    refs=[]
    for ref in oldrefs:
        # Full signal total is a stored analytical quantity, not estimated from counts.
        incident_total=ref['source_incident_per_pulse'] if 'source_incident_per_pulse' in ref else None
        if incident_total is None:
            # Sensor incidence is stored at the optical reference plane, independent of the gate.
            channel=len(refs);groups=np.asarray(result['optics']['pixel_group_ids'])
            photons=np.asarray(result['illumination']['signal_photons_per_pixel_per_pulse'])
            incident_total=float(photons[groups==channel].sum())
        budget=SimpleNamespace(signal_detected_per_pulse=ref['full_signal_total']/cfg.timing.laser_shots,
                               signal_sensor_incident_photons_per_pulse=incident_total)
        refs.append(signal_ground_truth(proxy,budget,edges,a))
    from ..processing.spatial_ranges import estimate_channels
    from ..reporting.noise_reference import rebin_noise_reference
    return {**({'noise_reference':rebin_noise_reference(result['noise_reference'],bin_ps)} if 'noise_reference' in result else {}),
            'histogram':histogram,'references':refs,'channel_ranges':estimate_channels(cfg,a,histogram),'statistics':{**stats,'lower':bounds['lower_counts'],'upper':bounds['upper_counts'],
             'trial_histograms':trials,'noise_histograms':noise,'noise_mean':np.mean(noise,axis=0).tolist() if noise else None},
            'processing_bin_ps':bin_ps,'note':'Rebinned original records and each saved replicate; no new random sampling.'}

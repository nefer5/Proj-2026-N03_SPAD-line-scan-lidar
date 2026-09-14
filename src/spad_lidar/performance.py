"""Bounded single-channel sweeps using the same simulator and detector."""
from math import ceil
import numpy as np
from .configuration import Algorithms
from .models import SimulationConfig
from .simulator import simulate, photon_budget
from .readout import readout_work_estimate


AXES={'range_m':'距离 (m)','solar_illuminance_lux':'太阳照度 (lux)','laser_shots':'累计脉冲数'}


def performance_sweep(config, axis, values):
    a=Algorithms.load()
    if axis not in AXES or not 1<=len(values)<=a.max_performance_sweep_points:
        raise ValueError('Invalid sweep axis or point count')
    if not config.detection_enabled or config.monte_carlo_trials<1:
        raise ValueError('Performance sweep requires detection enabled and at least one measurement trial')
    if len(set(values))!=len(values) or not all(np.isfinite(values)):
        raise ValueError('Sweep values must be finite and unique')
    if axis=='solar_illuminance_lux' and not config.solar_enabled:
        raise ValueError('Enable solar background before sweeping solar illuminance')
    seeds=np.random.SeedSequence(config.rng_seed).spawn(len(values)+1)[1:]
    configs=[];event_work=0;bin_work=0
    for value,seed in zip(values,seeds):
        if axis=='laser_shots':
            if value<1 or not float(value).is_integer():raise ValueError('Pulse sweep values must be positive integers')
            value=int(value)
        cfg=SimulationConfig.model_validate({**config.model_dump(),axis:value,'rng_seed':int(seed.generate_state(1)[0])})
        b=photon_budget(cfg)
        workload=readout_work_estimate(cfg,b,a)
        point_bins=ceil(cfg.gate_width_ns*1000/cfg.tdc_bin_ps)*workload['runs']
        if cfg.readout_mode!='analytic_reference':
            if workload['cycles']>a.max_readout_cycles or workload['events']>a.max_readout_expected_work:
                raise ValueError('Sweep point exceeds readout work limits; reduce pulses, flux or repetitions')
            event_work+=workload['events']
        if point_bins>a.max_detection_bin_work:
            raise ValueError('Sweep point exceeds detection histogram work limit')
        bin_work+=point_bins
        configs.append(cfg)
    if event_work>a.max_performance_sweep_work or bin_work>a.max_performance_sweep_bin_work:
        raise ValueError('Whole sweep exceeds configured work limit; reduce points or repetitions')
    points=[]
    for value,cfg in zip(values,configs):
        result=simulate(cfg)
        d=result['detection'];m=result['metrics'];b=result['budget']
        points.append({'value':value,'seed':cfg.rng_seed,'configuration_sha256':result['provenance']['sha256'],
                       'mode':cfg.readout_mode,'engine':result['readout']['engine'],
                       'threshold':d['threshold'],'pd':d['pd'],'pfa':d['pfa'],'trigger_rate':d['trigger_rate'],
                       'correct_range_rate':d['correct_range_rate'],
                       'failure_rate':1-d['correct_range_rate']['estimate'],
                       'bias_cm':m['bias_cm'],'precision_cm_1sigma':m['precision_cm_1sigma'],
                       'accepted_trials':m['valid_trials'],'trials':m['trials_completed'],
                       'mean_recorded_counts':sum(result['histogram']['expected_counts']),
                       'ideal_signal_candidates':result['histogram']['ground_truth']['in_gate_total'],
                       'background_candidates_per_gate':b['background_detected_per_gate']})
    return {'axis':axis,'axis_label':AXES[axis],'points':points,'configuration':config.model_dump(),
            'algorithms':a.model_dump(),'model_scope':'A_single_angular_channel',
            'note':'Every point runs the selected readout engine and independently calibrates its whole-gate threshold. Pd requires detection within truth tolerance; intervals are pointwise, conditional on that threshold. Not scanning dwell or a hardware maximum-range certification. Bias/precision include accepted ranges only; failures are reported separately.'}

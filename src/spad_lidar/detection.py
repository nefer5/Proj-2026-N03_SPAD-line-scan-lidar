"""Independent null calibration/evaluation and exact binomial intervals."""
from math import ceil
import numpy as np
from scipy.stats import beta


def binomial_interval(successes, trials, confidence):
    if not trials:
        return dict(successes=0,trials=0,estimate=None,ci_lower=None,ci_upper=None,confidence=confidence)
    tail=(1-confidence)/2
    lower=0.0 if successes==0 else float(beta.ppf(tail,successes,trials-successes+1))
    upper=1.0 if successes==trials else float(beta.ppf(1-tail,successes+1,trials-successes))
    return dict(successes=int(successes),trials=int(trials),estimate=successes/trials,
                ci_lower=lower,ci_upper=upper,confidence=confidence,method='Clopper-Pearson two-sided exact')


def calibrate_threshold(scores, target_pfa):
    scores=np.asarray(scores,dtype=float)
    if not len(scores) or not np.all(np.isfinite(scores)):
        raise ValueError('Calibration scores must be finite and nonempty')
    rank=ceil((len(scores)+1)*(1-target_pfa))
    if rank>len(scores):
        raise ValueError('Insufficient null calibration samples for target PFA')
    return float(np.sort(scores)[rank-1]),rank


def evaluate_detection(cfg, algorithms, observed, trials, noise_sampler, estimate_fn, signal_present):
    """Callbacks use the same histogram engine/search algorithm as acquisition.

    H0 calibration and held-out H0 evaluation never share RNG with H1 samples.
    Whole-gate maximum score calibrates the look-elsewhere/search effect.
    """
    seeds=np.random.SeedSequence(cfg.rng_seed).spawn(6)
    calibration_rng=np.random.default_rng(seeds[4])
    null_rng=np.random.default_rng(seeds[5])
    calibration_scores=[estimate_fn(noise_sampler(calibration_rng))[1]
                        for _ in range(algorithms.detector_calibration_trials)]
    threshold,rank=calibrate_threshold(calibration_scores,cfg.detection_target_pfa)
    def decide(hist):
        distance,score=estimate_fn(hist)
        detected=distance is not None and score>threshold
        return {'detected':bool(detected),'score':float(score),'raw_distance_m':distance,
                'distance_m':distance if detected else None}
    null_results=[decide(noise_sampler(null_rng)) for _ in range(algorithms.detector_null_trials)]
    observed_result=decide(observed)
    signal_results=[decide(hist) for hist in trials]
    accepted=[item['distance_m'] for item in signal_results]
    correct=sum(r is not None and abs(r-cfg.range_m)<=algorithms.success_tolerance_m for r in accepted)
    confidence=algorithms.probability_confidence_level
    pfa=binomial_interval(sum(item['detected'] for item in null_results),len(null_results),confidence)
    return {
        'enabled':True,'signal_present':bool(signal_present),'target_pfa':cfg.detection_target_pfa,
        'threshold':threshold,'comparison':'score > threshold; ties rejected',
        'score_definition':'maximum Gaussian-smoothed baseline-subtracted peak / background scale, searched over whole gate',
        'search_gate_ns':[cfg.gate_start_ns,cfg.gate_start_ns+cfg.gate_width_ns],
        'calibration':{'trials':len(calibration_scores),'order_statistic_rank':rank,'scores':calibration_scores,
                       'rng_spawn_key':list(seeds[4].spawn_key),'method':'finite-sample upper order statistic'},
        'null_evaluation':{'trials':len(null_results),'rng_spawn_key':list(seeds[5].spawn_key),
                           'scores':[item['score'] for item in null_results]},
        'observed':observed_result,'accepted_trial_estimates_m':accepted,
        'trial_scores':[item['score'] for item in signal_results],
        'pfa':pfa,
        'pfa_upper_within_target':pfa['ci_upper']<=cfg.detection_target_pfa,
        'pd':binomial_interval(correct,len(trials),confidence) if signal_present else None,
        'trigger_rate':binomial_interval(sum(item['detected'] for item in signal_results),len(trials),confidence),
        'correct_range_rate':binomial_interval(correct,len(trials),confidence),
        'pd_definition':'signal-present acquisition accepted AND estimated distance within configured truth tolerance',
        'pfa_definition':'probability of any accepted distance in a whole acquisition gate with signal disabled',
        'note':'Model-conditional MC calibration, not hardware certification. Calibration and null evaluation are independent. Intervals condition on the calibrated threshold; zero observed false alarms does not imply zero PFA. Pd is unavailable with zero signal budget or zero signal trials. Peak search never uses true target position.',
    }

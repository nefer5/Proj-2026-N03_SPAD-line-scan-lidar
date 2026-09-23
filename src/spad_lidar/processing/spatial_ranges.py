"""Apply the existing range estimator to each recorded channel, without truth input."""
from types import SimpleNamespace
import numpy as np
from .ranging import _estimate_range


def estimate_channels(cfg,algorithms,histogram):
    # These are known timing/calibration properties, not target truth or a truth ROI.
    estimator=SimpleNamespace(pulse_fwhm_ps=cfg.optics.pulse_fwhm_ps,pulse_shape=cfg.optics.pulse_shape,
        spad_jitter_fwhm_ps=cfg.device.spad_jitter_fwhm_ps,other_jitter_fwhm_ps=cfg.readout.other_jitter_fwhm_ps,
        tdc_bin_ps=histogram['bin_ps'],calibration_delay_ns=cfg.optics.calibration_delay_ns)
    rows=[]
    for channel,counts in enumerate(histogram['counts']):
        distance,score=_estimate_range(estimator,np.asarray(histogram['time_ns']),np.asarray(counts),algorithms)
        rows.append({'channel':channel,'recorded_counts':int(sum(counts)),'raw_distance_m':distance,'peak_score':score,
                     'detection_status':'unthresholded_estimate'})
    return {'rows':rows,'note':'Unthresholded full-gate estimates. No B-specific Pd/PFA calibration or detection claim; truth is excluded from estimator inputs.'}

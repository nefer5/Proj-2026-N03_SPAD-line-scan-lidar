"""Cheap static noise baseline; never mislabeled as post-readout output mean."""
import numpy as np


def candidate_noise_reference(source,groups,shots,gate_width_ns,bin_ps):
    optical=np.asarray(source['expected_optical_background_candidates_per_pixel_per_second'])
    rates=optical+source['expected_dark_candidates_per_pixel_per_second']+source['expected_other_candidates_per_pixel_per_second']
    by_channel=np.bincount(np.asarray(groups,dtype=int),weights=rates)
    reference={'method':'ideal_candidate_scalar','reference_plane':'after_PDE_FF_before_SPAD_dead_time_and_readout',
        'shots':shots,'gate_width_ns':gate_width_ns,'rate_cps_per_channel':by_channel.tolist(),
        'gate_counts_per_channel':(by_channel*shots*gate_width_ns*1e-9).tolist(),
        'includes':['optical_background_after_PDE_FF','dark_counts','other_device_noise'],
        'extra_acquisitions':0,
        'note':'Ideal noise candidate baseline per nominal time bin, accumulated over all measured exposures. '
               'No SPAD/TDC dead time, first-event competition, OR/coincidence or capacity losses. '
               'Not the noise contribution in mixed records, not a detection threshold. '
               'A partial last bin still uses nominal-bin normalization for this horizontal scalar.'}
    return rebin_noise_reference(reference,bin_ps)


def rebin_noise_reference(reference,bin_ps):
    if not np.isfinite(bin_ps) or bin_ps<=0:raise ValueError('Noise reference requires positive finite bin width')
    rates=np.asarray(reference['rate_cps_per_channel'])
    return {**reference,'bin_ps':bin_ps,'counts_per_bin':(rates*reference['shots']*bin_ps*1e-12).tolist()}

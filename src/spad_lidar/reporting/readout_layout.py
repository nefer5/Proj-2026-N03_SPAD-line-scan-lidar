"""Display geometry derived from the same pixel groups used by acquisition.

This describes complete pixel cells. Fill factor is a probability factor in the
current SPAD model; it does not define a fabricated photosensitive sub-pixel shape.
"""
import numpy as np


def channel_display_values(view):
    """Summarize saved sensor photons and records with acquisition's grouping.

    No PDE/FF or acquisition recalculation. A preview has no record_count field.
    """
    optics = view['optics']
    groups = np.asarray(optics['pixel_group_ids'])
    photons = np.asarray(view['illumination']['signal_photons_per_pixel_per_pulse'])
    cv, ch = optics['channel_shape']
    if photons.shape != groups.shape or not np.all(np.isfinite(photons)) or np.any(photons < 0):
        raise ValueError('Readout photon display requires one nonnegative finite value per pixel')
    values = np.bincount(groups, weights=photons, minlength=cv * ch)
    channels = [{'id': i, 'signal_photons_per_pulse': float(value)} for i, value in enumerate(values)]
    if 'histogram' in view:
        counts = np.asarray(view['histogram']['counts'])
        if counts.ndim != 2 or counts.shape[0] != len(channels):
            raise ValueError('Histogram channels disagree with readout layout')
        for channel, count in zip(channels, counts.sum(axis=1)):
            channel['record_count'] = int(count)
    return {'signal_peak': float(photons.max()), 'channels': channels,
            'reference_plane': 'sensor_incident_before_PDE_FF',
            'pixel_signal_unit': 'photons_per_physical_pixel_per_emitted_pulse',
            'channel_signal_unit': 'photons_per_channel_per_emitted_pulse'}


def readout_layout(optics):
    nv, nh = optics['array_shape']
    cv, ch = optics['channel_shape']
    groups = np.asarray(optics['pixel_group_ids']).reshape(nv, nh)
    rx = optics['dataset']['rx']
    x, y = rx['x_edges_um'], rx['y_edges_um']
    channels = []
    for v in range(cv):
        for h in range(ch):
            channel = v * ch + h
            rows, cols = np.nonzero(groups == channel)
            if not len(rows):
                raise ValueError(f'Readout channel {channel} contains no pixels')
            x0, x1 = int(cols.min()), int(cols.max()) + 1
            y0, y1 = int(rows.min()), int(rows.max()) + 1
            if not np.all(groups[y0:y1, x0:x1] == channel):
                raise ValueError('Readout display requires rectangular pixel groups')
            channels.append({'id': channel, 'h': h, 'v': v,
                             'pixels_h': x1 - x0, 'pixels_v': y1 - y0,
                             'spad_count': int(len(rows)),
                             'pixel_h_range': [x0, x1 - 1], 'pixel_v_range': [y0, y1 - 1],
                             'x_um': [x[x0], x[x1]], 'y_um': [y[y0], y[y1]]})
    return {'pixels_h': nh, 'pixels_v': nv, 'total_pixels': nh * nv,
            'channels_h': ch, 'channels_v': cv, 'total_channels': len(channels),
            'binning_h': channels[0]['pixels_h'], 'binning_v': channels[0]['pixels_v'],
            'spads_per_channel': channels[0]['spad_count'], 'channels': channels,
            'numbering': 'CH = V × N_H + H; H increases rightward, V increases upward.',
            'geometry_note': 'Full pixel cells; fill factor does not specify active-area geometry.'}

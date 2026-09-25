import numpy as np


def histogram_records(records, gate_start_ns, gate_width_ns, bin_ps, channel_count):
    return histogram_selected_records(records,gate_start_ns,gate_width_ns,bin_ps,range(channel_count))


def histogram_selected_records(records,gate_start_ns,gate_width_ns,bin_ps,channels):
    """Same binning contract with bounded, explicitly selected channel rows."""
    channels=list(channels)
    width = bin_ps*1e-3
    n = int(np.ceil(gate_width_ns/width))
    edges = gate_start_ns+np.arange(n+1)*width
    edges[-1] = gate_start_ns+gate_width_ns
    counts = np.zeros((len(channels), n), dtype=int)
    values={channel:[] for channel in channels}
    for record in records:
        if record['channel'] in values:values[record['channel']].append(record['phase_ns'])
    for row,channel in enumerate(channels):
        counts[row] = np.histogram(values[channel], bins=edges)[0]
    return {'edges_ns': edges.tolist(), 'time_ns': ((edges[:-1]+edges[1:])/2).tolist(),
            'counts': counts.tolist(), 'bin_ps': bin_ps}

import numpy as np


def histogram_records(records, gate_start_ns, gate_width_ns, bin_ps, channel_count):
    width = bin_ps*1e-3
    n = int(np.ceil(gate_width_ns/width))
    edges = gate_start_ns+np.arange(n+1)*width
    edges[-1] = gate_start_ns+gate_width_ns
    counts = np.zeros((channel_count, n), dtype=int)
    for channel in range(channel_count):
        values = [r['phase_ns'] for r in records if r['channel'] == channel]
        counts[channel] = np.histogram(values, bins=edges)[0]
    return {'edges_ns': edges.tolist(), 'time_ns': ((edges[:-1]+edges[1:])/2).tolist(),
            'counts': counts.tolist(), 'bin_ps': bin_ps}

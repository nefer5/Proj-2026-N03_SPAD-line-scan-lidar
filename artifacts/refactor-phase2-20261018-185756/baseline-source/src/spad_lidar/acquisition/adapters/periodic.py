"""Periodic record quantization, shared by direct SPAD, B and legacy C."""
import numpy as np
from ...spad.device import apply_jitter
from ...processing.records import histogram_records


def acquire_candidates(cfg,a,candidates,source_audit,pixel_groups,program,electronic_seed,progress,cancelled):
    """Shared state evolution, electronics response and quantized recording for B/C."""
    timing=cfg.timing
    if cancelled():
        raise InterruptedError('Cancelled before event acquisition')
    from ...spad.acquisition import evolve_program
    session=evolve_program(cfg.device,cfg.readout,pixel_groups,program,candidates,a,progress,cancelled)
    by_cycle={w.cycle:w for w in program.windows}
    records = session.readout.records
    jittered = apply_jitter(np.random.default_rng(electronic_seed), np.array([r['phase_ns'] for r in records]), cfg.readout.other_jitter_fwhm_ps)
    bin_width_ns = cfg.readout.tdc_bin_ps*1e-3
    measured = []
    for r, phase in zip(records, jittered):
        effective_close=min(timing.gate_start_ns+timing.gate_width_ns,program.windows[-1].end_ns-by_cycle[r['cycle']].start_ns)
        if timing.gate_start_ns <= phase < effective_close:
            code = int(np.floor((phase-timing.gate_start_ns)/bin_width_ns))
            left = timing.gate_start_ns+code*bin_width_ns
            right = min(left+bin_width_ns, effective_close)
            measured.append({'cycle': r['cycle'], 'channel': r['channel'], 'tdc': r['tdc'], 'tdc_code': code,
                             'phase_ns': (left+right)/2, 'interval_start_ns': left, 'interval_end_ns': right})
    histogram = histogram_records(measured, timing.gate_start_ns, timing.gate_width_ns, cfg.readout.tdc_bin_ps,
                                  int(np.max(pixel_groups))+1)
    audit = {**session.stats, 'timestamp_outside_gate_losses': len(records)-len(measured),
             'final_records': len(measured), 'source': source_audit, 'trace': session.readout.trace,
             'trace_truncated': session.stats['logic_triggers'] > len(session.readout.trace)}
    return {'records': measured, 'histogram': histogram, 'audit': audit,
            'record_schema': {'version': 1, 'time_basis': 'cycle-relative ns', 'tdc_bin_ps': cfg.readout.tdc_bin_ps,
                              'pixel_identity': 'not exported beyond hardware TDC identity',
                              'replay': 'Rebin only at integer multiples of original bin width with original gate origin.'}}


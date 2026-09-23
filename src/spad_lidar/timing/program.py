from ..contracts import AcquisitionProgram, AcquisitionWindow


def periodic_program(period_ns, gate_start_ns, gate_width_ns, first_cycle, end_cycle, measured_shots):
    return AcquisitionProgram([
        AcquisitionWindow(c, c*period_ns, (c+1)*period_ns, c*period_ns+gate_start_ns,
                          c*period_ns+gate_start_ns+gate_width_ns, 0 <= c < measured_shots,
                          c*period_ns+gate_start_ns, c*period_ns+gate_start_ns+gate_width_ns)
        for c in range(first_cycle, end_cycle)
    ])

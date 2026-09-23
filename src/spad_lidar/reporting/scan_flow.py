from ..configuration import read_yaml


def build_scan_flow(cfg,info,projector,result,gate_exposure_s):
    b=info['budget'];t=projector.budget_totals;gate_s=cfg.timing.gate_width_ns*1e-9
    ranges=[value for row in projector.trace if row['emitted'] for value in row['ray_reflection_ranges_m']]
    values={
        'scheduled_slots':result['scan']['summary']['scheduled_slots'],
        'emitted_reference_slots':projector.emission_count,
        'reference_tx_input_energy_j':cfg.optics.total_pulse_energy_nj*1e-9*projector.emission_count,
        'reference_tx_angular_truncation_j':info['budget']['tx_angular_truncation_j']*projector.emission_count,
        'actual_tx_average_power_w':result['scan']['frame_budget']['actual_tx_average_power_w'],
        'actual_tx_output_energy_j':result['scan']['frame_budget']['actual_tx_output_energy_j'],
        'center_accounted_tx_output_energy_j':result['scan']['frame_budget']['center_accounted_tx_output_energy_j'],
        'target_incident_j':t['target_incident_j'],'target_reflected_j':t['target_reflected_j'],
        'assigned_pulses':result['scan']['summary']['assigned_pulses'],
        'true_useful_pulses':result['scan']['summary']['true_useful_pulses'],
        'duration_ns':result['scan']['frame_budget']['duration_ns'],
        'gate_exposure_s':gate_exposure_s,
        'signal_pupil_photons_total':t['pupil_j']/projector.photon_j,
        'signal_sensor_photons_total':t['sensor_j']/projector.photon_j,
        'signal_candidates_total':t['sensor_j']/projector.photon_j*projector.signal_response,
        'pupil_energy_j':t['pupil_j'],'sensor_energy_j':t['sensor_j'],
        'rx_loss_j':t['rx_loss_j'],'filter_loss_j':t['filter_loss_j'],'edge_loss_j':t['edge_loss_j'],
        'energy_balance_residual_j':t['pupil_j']-sum(t[k] for k in ('sensor_j','rx_loss_j','filter_loss_j','edge_loss_j')),
        'final_mixed_records':result['audit']['final_records'],
        'angle_assigned_records':result['scan']['summary']['retained_records'],
        'reflection_range_min_m':min(ranges) if ranges else None,
        'reflection_range_max_m':max(ranges) if ranges else None,
    }
    for name in ('solar','other'):
        for plane in ('rx_incident_photons','sensor_incident_photons','candidate_avalanches'):
            values[f'{name}_{plane}_total']=b[f'{name}_{plane}_per_gate']/gate_s*gate_exposure_s
    definition=read_yaml('photon-flow.yaml')['scan'];formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    return {'title':definition['title'],'intro':definition['intro'],
        'background_integration_band_nm':b['background_integration_band_nm'],'values':values,
        'steps':[{**step,'latex':formulas[step['formula_id']],'symbols':notes[step['formula_id']],
                  'values':[{**v,'value':values[v['key']]} for v in step['values']]} for step in definition['steps']]}

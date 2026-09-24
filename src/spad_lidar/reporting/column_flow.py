"""Bind column energy audit to the existing shared C photon-flow definitions."""
from ..configuration import read_yaml
from ..spad.device import effective_pde
from ..curves import Curve
from ..constants import H,C


def build_column_flow(cfg,result):
    s=result['column_scan'];t=s['signal_budget_total'];b=result['optics']['budget'];fb=s['frame_budget']
    photon=H*C/(cfg.tx.wavelength_nm*1e-9)
    response=effective_pde(Curve(cfg.spectral_inputs.pde)(cfg.tx.wavelength_nm),cfg.spad.fill_factor)
    gates=fb['gate_union_exposure_ns']*1e-9;gate_s=cfg.timing.gate_width_ns*1e-9
    values={'scheduled_slots':len(s['schedule']),'column_count':fb['measured_column_count'],'trigger_count':fb['trigger_count'],'emitted_reference_slots':fb['emission_count'],
        'reference_tx_input_energy_j':fb['input_energy_of_measured_sources_j'],
        'reference_tx_angular_truncation_j':fb['input_energy_of_measured_sources_j']*cfg.tx.tx_efficiency*(1-b['tx_angular_coverage_fraction']),
        'actual_tx_average_power_w':fb['tx_average_power_w'],'actual_tx_output_energy_j':fb['tx_output_energy_in_observation_j'],
        'center_accounted_tx_output_energy_j':fb['center_accounted_tx_output_energy_j'],
        'target_incident_j':t['target_incident_j'],'target_reflected_j':t['target_reflected_j'],
        'assigned_pulses':fb['trigger_count'],'true_useful_pulses':sum(r['emitted'] and r['true_active'] for r in s['schedule']),
        'duration_ns':fb['observation_duration_ns'],'gate_exposure_s':gates,
        'signal_pupil_photons_total':t['pupil_j']/photon,'signal_sensor_photons_total':t['sensor_j']/photon,
        'signal_candidates_total':t['sensor_j']/photon*response,'pupil_energy_j':t['pupil_j'],'sensor_energy_j':t['sensor_j'],
        'rx_loss_j':t['rx_loss_j'],'filter_loss_j':t['filter_loss_j'],'edge_loss_j':t['edge_loss_j'],
        'energy_balance_residual_j':t['pupil_j']-sum(t[k] for k in ('sensor_j','rx_loss_j','filter_loss_j','edge_loss_j')),
        'final_mixed_records':result['audit']['final_records'],'angle_assigned_records':s['summary']['retained_analysis_records'],
        'reflection_range_min_m':min((r['range_min_m'] for r in s['pulse_optical_audit'] if r['measured']),default=None),
        'reflection_range_max_m':max((r['range_max_m'] for r in s['pulse_optical_audit'] if r['measured']),default=None)}
    for name in ('solar','other'):
        for plane in ('rx_incident_photons','sensor_incident_photons','candidate_avalanches'):
            values[f'{name}_{plane}_total']=b[f'{name}_{plane}_per_gate']/gate_s*gates
    spec=read_yaml('photon-flow.yaml')['columns'];f=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    return {'title':spec['title'],'intro':spec['intro'],
        'background_integration_band_nm':b['background_integration_band_nm'],'values':values,
        'steps':[{**step,'latex':f[step['formula_id']],'symbols':notes[step['formula_id']],
                  'values':[{**v,'value':values[v['key']]} for v in step['values']]} for step in spec['steps']]}

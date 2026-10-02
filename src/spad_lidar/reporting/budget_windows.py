"""Single angular-channel temporal windows, using the shared pulse core."""
import numpy as np
from ..numerics.temporal import pulse_interval_fractions,temporal_pdf
from ..configuration import read_yaml
from ..constants import H,C


def channel_windows(cfg,budget,arrival_ns,algorithms):
    tx=cfg.tx;gate=cfg.acquisition
    width=tx.pulse_fwhm_ps*1e-3
    pulse_low,pulse_high=arrival_ns-width/2,arrival_ns+width/2
    gate_low,gate_high=gate.gate_start_ns,gate.gate_start_ns+gate.gate_width_ns
    width_fraction=float(pulse_interval_fractions(0.,-width/2,width/2,tx.pulse_shape,tx.pulse_fwhm_ps))
    noise_rate=cfg.spad.spads_per_channel*(cfg.spad.dcr_cps_per_spad+cfg.spad.other_noise_cps_per_spad)
    def window(key,label,low,high):
        duration=max(0.,high-low)
        fraction=0. if duration==0 else float(pulse_interval_fractions(arrival_ns,low,high,tx.pulse_shape,tx.pulse_fwhm_ps))
        return {'key':key,'label':label,'start_ns':low,'end_ns':high,'duration_ns':duration,'signal_fraction':fraction,
            'signal_pupil_photons':budget['signal_rx_incident_photons_per_pulse']*fraction,
            'signal_sensor_photons':budget['signal_sensor_incident_photons_per_pulse']*fraction,
            'solar_pupil_photons':budget['solar_rx_incident_photons_per_gate']*duration/gate.gate_width_ns,
            'other_pupil_photons':budget['other_rx_incident_photons_per_gate']*duration/gate.gate_width_ns,
            'solar_sensor_photons':budget['solar_sensor_incident_photons_per_gate']*duration/gate.gate_width_ns,
            'other_sensor_photons':budget['other_sensor_incident_photons_per_gate']*duration/gate.gate_width_ns,
            'signal_candidates':budget['signal_candidate_avalanches_per_pulse']*fraction,
            'signal_pupil_energy_nj':budget['rx_pupil_signal_j']*1e9*fraction,
            'signal_sensor_energy_nj':budget['sensor_signal_j']*1e9*fraction,
            'solar_candidates':budget['solar_candidate_rate_cps']*duration*1e-9,
            'other_candidates':budget['other_candidate_rate_cps']*duration*1e-9,
            'background_candidates':(budget['solar_candidate_rate_cps']+budget['other_candidate_rate_cps'])*duration*1e-9,
            'device_noise_candidates':noise_rate*duration*1e-9,'final_mixed_records':None}
    windows=[window('gate','一个接收gate',gate_low,gate_high),
             window('pulse_width','回波中心 ± 等效脉宽/2',pulse_low,pulse_high)]
    low=max(gate_low,pulse_low);high=min(gate_high,pulse_high)
    windows.append(window('intersection','gate与等效脉宽窗口的交集',low,max(low,high)))
    half=width*algorithms.budget_pulse_plot_half_widths
    offsets=np.linspace(-half,half,algorithms.budget_temporal_plot_samples)
    if tx.pulse_shape=='rectangular':
        offsets=np.unique(np.r_[offsets,-width/2,width/2,np.nextafter(-width/2,-np.inf),np.nextafter(width/2,np.inf)])
    pdf=temporal_pdf(offsets,tx.pulse_shape,tx.pulse_fwhm_ps)
    fractions= pulse_interval_fractions(0.,offsets[0],offsets,tx.pulse_shape,tx.pulse_fwhm_ps)
    gate_clip=[max(-half,gate_low-arrival_ns),min(half,gate_high-arrival_ns)]
    if gate_clip[1]<gate_clip[0]:gate_clip=None
    result={'windows':windows,'arrival_ns':arrival_ns,'equivalent_width_ns':width,'shape':tx.pulse_shape,
        'tx_total_energy_nj':budget['tx_input_j']*1e9,'tx_width_energy_nj':budget['tx_input_j']*1e9*width_fraction,
        'width_energy_fraction':width_fraction,'tx_peak_w':float(budget['tx_input_j']*1e9*temporal_pdf(0.,tx.pulse_shape,tx.pulse_fwhm_ps)),
        'tx_width_average_w':budget['tx_input_j']*1e9*width_fraction/width,
        'profile':{'offset_ns':offsets.tolist(),'power_w':(pdf*budget['tx_input_j']*1e9).tolist(),
                   'normalized_density':(pdf/float(pdf.max())).tolist(),'cumulative_fraction':fractions.tolist(),
                   'echo_candidate_density_per_ns':(pdf*budget['signal_candidate_avalanches_per_pulse']).tolist(),
                   'gate_clip_relative_ns':gate_clip,'width_bounds_ns':[-width/2,width/2]},
        'scope_note':'一个独立角通道、一次发射。脉宽窗口以回波中心为中心；高斯FWHM窗不是全脉冲能量。未计器件抖动、死时间、跨发尾部或数字读出损失。'}
    chain=read_yaml('photon-flow.yaml')['budget_signal_chain']
    photon_j=H*C/(tx.wavelength_nm*1e-9)
    result['signal_chain']={'title':chain['title'],'intro':chain['intro'],'stages':[{**stage,'energy_nj':budget[stage['key']]*1e9 if stage['kind']=='optical' else None,'photons_or_candidates':budget[stage['key']]/photon_j if stage['kind']=='optical' else budget[stage['key']]} for stage in chain['stages']],'final_mixed_records':None}
    definition=read_yaml('photon-flow.yaml')['budget_window'];formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    for w in windows:
        w['flow']=[{**step,'latex':formulas[step['formula_id']],'symbols':notes[step['formula_id']],
            'values':[{**value,'value':w[value['key']]} for value in step['values']]} for step in definition['steps']]
    return result

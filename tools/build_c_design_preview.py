"""Build design-only C data from the existing scheduler and common waveform core.

No new exposure, tail, queue or bandwidth model is implemented here. The only
production input change in this review is the user-requested 2×16 array default.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
import hashlib,json,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.scan.schedule import build_schedule
from spad_lidar.scan.aggregation import count_pulses
from spad_lidar.reporting.a_view import laser_quantities
from spad_lidar.experiments.a_signal import _signal_pdf,timing_sigma_ns
from spad_lidar.constants import C
from spad_lidar import __version__

OUT=ROOT/'web/prototypes/c-exposure'


def build():
    cfg=SimulationConfig.for_experiment('scan',{})
    a=Algorithms.load();program,schedule,edges,budget=build_schedule(cfg,a)
    rows=[r for r in schedule if r['measured'] and r['frame']==0]
    counts=count_pulses(schedule,cfg.scan.frame_count,budget['frame_period_ns'],len(edges)-1)
    # This fixture explicitly uses the current uniform forward-scan case. It is
    # not a general column scheduler or a rule equating columns with angle bins.
    if cfg.scan.trajectory!='sawtooth' or cfg.scan.emission_policy!='active_only':
        raise ValueError('Design baseline needs the documented uniform forward-scan reference')
    columns=[]
    for i in range(len(edges)-1):
        pulses=[r for r in rows if r['emitted'] and r['assigned_bin']==i]
        if not pulses:raise ValueError('Reference angle cell has no enabled pulses')
        columns.append({'index':i,'angle_min_mrad':float(edges[i]),'angle_max_mrad':float(edges[i+1]),
            'angle_center_mrad':float((edges[i]+edges[i+1])/2),'start_ns':pulses[0]['nominal_time_ns'],
            'end_ns':pulses[-1]['slot_end_ns'],'pulses':pulses})
    proxy=SimpleNamespace(pulse_shape=cfg.tx.pulse_shape,pulse_fwhm_ps=cfg.tx.pulse_fwhm_ps,
        pulse_energy_nj=cfg.tx.total_pulse_energy_nj,laser_prf_hz=budget['prf_hz'],
        laser_shots=len(columns[0]['pulses']),range_m=cfg.scene.range_m,
        calibration_delay_ns=cfg.acquisition.calibration_delay_ns,
        spad_jitter_fwhm_ps=cfg.spad.spad_jitter_fwhm_ps,other_jitter_fwhm_ps=cfg.readout.other_jitter_fwhm_ps)
    laser=laser_quantities(proxy,a)
    tof=2*cfg.scene.range_m/C*1e9+cfg.acquisition.calibration_delay_ns
    spread=a.ground_truth_extent_sigma*timing_sigma_ns(proxy)
    echo_time=np.linspace(tof-spread,tof+spread,a.ground_truth_plot_points)
    echo_pdf=_signal_pdf(proxy,echo_time)
    slots=len(columns);lines=cfg.spad.channels_v;routes=cfg.spad.channels_h
    data={'schema_version':1,'purpose':'design_review_only',
        'provenance':{'utc':datetime.now(timezone.utc).isoformat(),'model_version':__version__,
                      'configuration_sha256':hashlib.sha256(json.dumps(cfg.model_dump(),sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                      'algorithm_sha256':hashlib.sha256(json.dumps(a.model_dump(),sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                      'source':'SimulationConfig, build_schedule, count_pulses, laser_quantities, shared analytical IRF',
                      'note':'Only the regular schedule and waveform reference are numeric. New strategies, long tails, internal states and bandwidth queues are not simulated.'},
        'configuration':cfg.model_dump(),'algorithm_configuration':a.model_dump(),
        'columns':columns,'frame_rows':rows,'frame_budget':budget,
        'assigned_counts':counts['assigned'][0].tolist(),'true_counts':counts['true_useful'][0].tolist(),
        'line_rows':lines,'h_routes':routes,'physical_shape':[lines*cfg.device.V_binning,routes*cfg.device.H_binning],
        'timing':{'trigger_period_ns':cfg.timing.period_ns,'gate_offset_ns':cfg.timing.gate_start_ns,
                  'gate_width_ns':cfg.timing.gate_width_ns,'pulse_fwhm_ns':cfg.tx.pulse_fwhm_ps*1e-3,
                  'spad_dead_time_ns':cfg.device.spad_dead_time_ns,'tdc_bin_ns':cfg.readout.tdc_bin_ps*1e-3,
                  'tof_ns':tof,'range_m':cfg.scene.range_m,'range_bin_m':C*cfg.readout.tdc_bin_ps*1e-12/2},
        'waveforms':{'tx_time_ns':(np.asarray(laser['pulse']['time_ps'])*1e-3).tolist(),
                     'tx_power_w':laser['pulse']['power_w'],'echo_phase_ns':echo_time.tolist(),
                     'echo_relative':(echo_pdf/echo_pdf.max()).tolist()},
        'planning_reference':{'frame_period_ns':budget['frame_period_ns'],'active_ns':budget['frame_period_ns']*cfg.scan.active_fraction,
            'flyback_ns':budget['frame_period_ns']*(1-cfg.scan.active_fraction),'h_fov_mrad':float(edges[-1]-edges[0]),
            'angle_step_mrad':cfg.scan.angle_bin_width_mrad,'column_count':slots,'points_per_frame_one_H':lines*slots,
            'points_per_second_one_H':lines*slots*cfg.scan.frame_rate_hz,'points_per_frame_all_H':routes*lines*slots,
            'unknown':['output_format','payload_bits','column_header_bytes','frame_header_bytes','protocol_overhead','link_net_rate','buffer_capacity','processing_latency']}}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'reference.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf8')


def fingerprint():
    template=(OUT/'index.template.html').read_text(encoding='utf8')
    for name in ('design.css','design.js','reference.json'):
        digest=hashlib.sha256((OUT/name).read_bytes()).hexdigest()[:16]
        template=template.replace('{{'+name+'}}',name+'?v='+digest)
    (OUT/'index.html').write_text(template,encoding='utf8')


if __name__=='__main__':
    if '--assets-only' not in sys.argv:build()
    if (OUT/'index.template.html').exists():fingerprint()

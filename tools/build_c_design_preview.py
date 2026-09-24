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
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.scan.schedule import build_schedule
from spad_lidar.scan.aggregation import count_pulses
from spad_lidar.scan.trajectory import mirror_pose
from spad_lidar.scene.scan_target import reflection_range
from spad_lidar.rx.spatial import image_center
from spad_lidar.reporting.a_view import laser_quantities
from spad_lidar.experiments.a_signal import _signal_pdf,timing_sigma_ns
from spad_lidar.constants import C
from spad_lidar import __version__

OUT=ROOT/'web/prototypes/c-exposure'


def high_level_reference(cfg, column_count, frame_period_ns, hfov_mrad):
    """Uniform budget illustration only; never modifies the scan or detector plan."""
    scan_ns=frame_period_ns*cfg.scan.active_fraction
    slot_ns=scan_ns/column_count
    formula_ids=('c_high_level_frame','c_high_level_slot','c_high_level_angle')
    formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    inputs={'frame_rate_hz':cfg.scan.frame_rate_hz,'hfov_mrad':hfov_mrad,
            'scan_time_utilization':cfg.scan.active_fraction,'slot_count':column_count}
    return {'inputs':inputs,'allocation':'uniform_equal_share',
        'derived':{'frame_period_ns':frame_period_ns,'scan_allocatable_ns':scan_ns,
            'non_scan_ns':frame_period_ns-scan_ns,'slot_max_ns':slot_ns,'slot_target_ns':slot_ns,
            'angle_per_slot_mrad':hfov_mrad/column_count,'hfov_deg':float(np.degrees(hfov_mrad*1e-3)),
            'required_average_optical_rad_s':hfov_mrad*1e6/(column_count*slot_ns)},
        'target_source':'high_level_system_budget','scope':'design_review_reference_only',
        'input_sha256':hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'formulas':[{ 'id':fid,'latex':formulas[fid],'note':notes[fid]} for fid in formula_ids],
        'limitations':['Uniform equal slots; no extra margin is reserved in this illustration.',
            'Current scan.active_fraction supplies the reference utilization. Additional hardware overhead is not known.',
            'HFOV means angular-cell coverage; angular width per slot uses N, not N-1.',
            'Target is a requirement, not proof of DSP, MIPI, buffering or ranging feasibility.']}


def motion_reference(cfg, algorithms, columns, frame_period_ns):
    """Audit existing scan geometry; no new transport or detector model.

    Range comparisons vary only the base scene distance. The same scene-motion,
    mirror-pose and inverted-image mapping functions used by C/B are reused.
    Electronic calibration delay is intentionally excluded from mirror motion.
    """
    times=np.unique(np.r_[np.linspace(0,frame_period_ns,algorithms.pulse_preview_points),
                          [p['emission_time_ns'] for c in columns for p in c['pulses']]])
    mechanical,optical,velocity,_=mirror_pose(cfg.scan,times)
    ranges=sorted(set(algorithms.performance_sweep_range_values+[cfg.scene.range_m]))
    motions=[]
    for column in columns:
        shot_times=np.array([p['emission_time_ns'] for p in column['pulses']])
        mech,tx,vel,_=mirror_pose(cfg.scan,shot_times)
        _,boundary_angles,_,_=mirror_pose(cfg.scan,[column['start_ns'],column['end_ns']])
        rows=[]
        for i,pulse in enumerate(column['pulses']):
            comparisons=[]
            for base_range in ranges:
                optical_cfg=SimpleNamespace(**{**cfg.optics.model_dump(),'range_m':base_range})
                distance=float(reflection_range(optical_cfg,cfg.scene_motion,tx[i],shot_times[i]))
                tof=2*distance/C*1e9
                _,rx0,_,_=mirror_pose(cfg.scan,shot_times[i])
                _,rx1,_,_=mirror_pose(cfg.scan,shot_times[i]+tof)
                rx0=float(rx0)*cfg.scan.rx_scan_scale+cfg.scan.rx_angle_offset_mrad
                rx1=float(rx1)*cfg.scan.rx_scan_scale+cfg.scan.rx_angle_offset_mrad
                relative=float(tx[i])-rx1
                x=float(image_center(cfg.optics,relative,0)[0])
                x_at_emit=float(image_center(cfg.optics,float(tx[i])-rx0,0)[0])
                comparisons.append({'base_range_m':base_range,'reflection_range_m':distance,
                    'flight_ns':tof,'arrival_ns':float(shot_times[i]+tof),'rx_axis_at_emit_mrad':rx0,
                    'rx_axis_at_return_mrad':rx1,'rx_motion_mrad':rx1-rx0,
                    'relative_rx_h_mrad':relative,'image_x_um':x,'motion_image_shift_um':x-x_at_emit})
            rows.append({'cycle':pulse['cycle'],'offset_ns':float(shot_times[i]-column['start_ns']),
                'mechanical_mrad':float(mech[i]),'tx_mrad':float(tx[i]),
                'mechanical_rad_s':float(vel[i]/cfg.scan.optical_multiplier*1e6),
                'optical_rad_s':float(vel[i]*1e6),
                'dt_previous_ns':None if i==0 else float(shot_times[i]-shot_times[i-1]),
                'dtx_previous_mrad':None if i==0 else float(tx[i]-tx[i-1]),'returns':comparisons})
        motions.append({'column_index':column['index'],'pulse_rows':rows,
            'slot_travel_mrad':float(boundary_angles[1]-boundary_angles[0]),
            'first_to_last_mrad':float(tx[-1]-tx[0])})
    return {'source':'Existing mirror_pose + reflection_range + image_center, central Tx ray (local H=V=0)',
        'range_sampling_source':'algorithms.performance_sweep_range_values plus scene.range_m',
        'range_values_m':ranges,'time_ns':times.tolist(),'mechanical_mrad':mechanical.tolist(),
        'tx_mrad':optical.tolist(),'mechanical_rad_s':(velocity/cfg.scan.optical_multiplier*1e6).tolist(),
        'optical_rad_s':(velocity*1e6).tolist(),'columns':motions,
        'limitations':['Central ray only; not a new PSF capture or detection simulation.',
            'Current core evaluates Rx pose at echo centers; finite-pulse scan smear is not expanded.',
            'Static optical mapping means unchanged PSF kernel, not unchanged energy captured by each channel.',
            'Return angle excludes electronic calibration delay. Use exact pose differences across trajectory turns.']}


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
                      'source':'SimulationConfig, build_schedule, count_pulses, laser_quantities, shared analytical IRF, mirror_pose, reflection_range, image_center',
                      'note':'Regular schedule, waveforms and motion/range geometry use existing Python functions. Edited pulse lists and DSP/MIPI intervals are UI drafts; new strategies, long tails, internal states and transport queues are not simulated.'},
        'configuration':cfg.model_dump(),'algorithm_configuration':a.model_dump(),
        'columns':columns,'frame_rows':rows,'frame_budget':budget,
        'motion':motion_reference(cfg,a,columns,budget['frame_period_ns']),
        'high_level':high_level_reference(cfg,slots,budget['frame_period_ns'],float(edges[-1]-edges[0])),
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
    for name in ('design.css','high-level.js','review-v2.js','design.js','reference.json'):
        digest=hashlib.sha256((OUT/name).read_bytes()).hexdigest()[:16]
        template=template.replace('{{'+name+'}}',name+'?v='+digest)
    for name in ('katex.min.js','katex.min.css'):
        path=ROOT/'web/vendor/katex'/name
        digest=hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        template=template.replace('{{'+name+'}}','/static/vendor/katex/'+name+'?v='+digest)
    (OUT/'index.html').write_text(template,encoding='utf8')


if __name__=='__main__':
    if '--assets-only' not in sys.argv:build()
    if (OUT/'index.template.html').exists():fingerprint()

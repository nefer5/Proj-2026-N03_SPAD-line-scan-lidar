import json,runpy
import numpy as np
ns=runpy.run_path('tools/build_c_design_preview.py')
Cfg,A,C=ns['SimulationConfig'],ns['Algorithms'],ns['C']
d=json.load(open('web/prototypes/c-exposure/reference.json',encoding='utf8'))
cfg=Cfg.for_experiment('scan',{});a=A.load();build=ns['motion_reference'];cols=d['columns'];motion=d['motion']
p=motion['columns'][7]['pulse_rows'][-1]
r=next(r for r in p['returns'] if r['base_range_m']==cfg.scene.range_m)
np.testing.assert_allclose(p['optical_rad_s'],cfg.scan.optical_multiplier*p['mechanical_rad_s'])
np.testing.assert_allclose(p['dtx_previous_mrad'],p['optical_rad_s']*p['dt_previous_ns']*1e-6)
np.testing.assert_allclose(r['flight_ns'],2*r['reflection_range_m']/C*1e9)
np.testing.assert_allclose(r['relative_rx_h_mrad'],p['tx_mrad']-r['rx_axis_at_return_mrad'])
np.testing.assert_allclose(r['rx_motion_mrad'],p['optical_rad_s']*r['flight_ns']*1e-6)
assert r['motion_image_shift_um']>0 and r['relative_rx_h_mrad']<0
static=build(Cfg.for_experiment('scan',{'scan':{'trajectory':'static'}}),a,cols,d['frame_budget']['frame_period_ns'])
assert all(r['rx_motion_mrad']==0 for c in static['columns'] for p in c['pulse_rows'] for r in p['returns'])
cal=build(Cfg.for_experiment('scan',{'acquisition':{'calibration_delay_ns':123}}),a,cols,d['frame_budget']['frame_period_ns'])
assert cal==motion,'Electronic calibration must not change mechanical flight geometry'
# A hypothetical far target crosses the known sawtooth turning instant.
far=C*20e-6/2
far_a=a.model_copy(update={'performance_sweep_range_values':[far]})
turn=build(cfg,far_a,cols,d['frame_budget']['frame_period_ns'])['columns'][-1]['pulse_rows'][-1]
rr=next(r for r in turn['returns'] if r['base_range_m']==far)
assert not np.isclose(rr['rx_motion_mrad'],turn['optical_rad_s']*rr['flight_ns']*1e-6),'Must evaluate actual return pose across turnaround'
print(json.dumps({'status':'passed','checks':['units','angular multiplier','emission displacement','signed Rx incidence','inverted image shift','static mirror limit','calibration excluded from flight','exact turnaround pose'],'reference':{'mechanical_rad_s':p['mechanical_rad_s'],'optical_rad_s':p['optical_rad_s'],'pulse_delta_mrad':p['dtx_previous_mrad'],'flight_ns':r['flight_ns'],'rx_shift_mrad':r['rx_motion_mrad'],'image_shift_um':r['motion_image_shift_um']}},ensure_ascii=False,indent=2))
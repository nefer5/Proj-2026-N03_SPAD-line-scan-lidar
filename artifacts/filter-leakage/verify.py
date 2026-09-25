"""Same saved case: zero-leakage compatibility and broadband optical audit."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.experiments.spatial import run_system,project_illumination
from spad_lidar.spad.device import effective_pde
from spad_lidar.curves import Curve
from spad_lidar.constants import C,H
JOB='3440493ef4be44c98130ae74e1451805'
p=ROOT/'artifacts/runs'/JOB/'result.json';old=json.loads(p.read_text(encoding='utf-8'))
a=Algorithms.from_snapshot(old['configuration']['algorithms'])
cfg=SimulationConfig.for_experiment('system',old['configuration']['experiment'],a)
zero=run_system(cfg,a,lambda *_:None,lambda:False)
assert zero['records']==old['records']
np.testing.assert_array_equal(zero['illumination']['signal_photons_per_pixel_per_pulse'],old['illumination']['signal_photons_per_pixel_per_pulse'])
values=cfg.model_dump();values['spectral_inputs']['filter']['basic']['out_of_band_transmission']=.001
leak_cfg=SimulationConfig.for_experiment('system',values,a)
light,groups,info=project_illumination(leak_cfg,a,lambda *_:None,lambda:False)
s=info['spectral_integration'];b=info['budget'];wl=np.array(s['wavelength_nm'])
q=np.array(s['weights_nm'])*wl*1e-9/(H*C);t=np.array(s['filter_transmission'])
sun=np.array(s['solar_radiance_w_m2_sr_nm']);response=effective_pde(Curve(leak_cfg.spectral_inputs.pde)(wl),leak_cfg.device.fill_factor)
factor=np.array(s['solar_sensor_photons_per_second_per_spectral_cell']['pixel_factor']).sum()
independent=float(factor*np.dot(sun*q*t,response))
np.testing.assert_allclose(independent,b['solar_candidate_rate_cps'],rtol=1e-12)
report={'utc':datetime.now(timezone.utc).isoformat(),'source_job':JOB,'source_result_sha256':sha256(p.read_bytes()).hexdigest(),
 'zero_configuration':zero['configuration'],'zero_provenance':zero['provenance'],'zero_budget':zero['optics']['budget'],
 'leakage_configuration':leak_cfg.model_dump(),'leakage_budget':b,'domain':s['domain'],
 'storage':{key:s[key] for key in ('storage','integration_work','logical_cells','stored_cells_per_measure')},
 'checks':{'zero_leakage_records_exactly_preserved':True,'zero_leakage_signal_exactly_preserved':True,'independent_spectral_integral_matches':True},
 'meaning':'Displayed time-bin values are analytical candidate rates after PDE/FF multiplied by bin duration; no gate/exposure/repetition statistics.'}
Path(__file__).with_name('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
Path(__file__).with_name('leakage-example-config.json').write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':report['checks'],'zero_bin':zero['optics']['budget']['solar_mean_candidates_per_time_bin'],'leak_bin':b['solar_mean_candidates_per_time_bin'],'domain':s['domain'],'storage':report['storage']},ensure_ascii=False,indent=2))

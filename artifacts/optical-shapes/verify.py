"""Preserve the user's isotropic Gaussian acquisition while extending the model."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.experiments.spatial import run_system,project_illumination
from spad_lidar.reporting.spatial_view import optical_view
JOB='90e9141e1ad34cf3b21a693788a1de41'
path=ROOT/'artifacts/runs'/JOB/'result.json';old=json.loads(path.read_text(encoding='utf-8'))
a=Algorithms.from_snapshot(old['configuration']['algorithms'])
cfg=SimulationConfig.for_experiment('system',old['configuration']['experiment'],a)
new=run_system(cfg,a,lambda *_:None,lambda:False)
assert new['records']==old['records']
np.testing.assert_array_equal(new['illumination']['signal_photons_per_pixel_per_pulse'],old['illumination']['signal_photons_per_pixel_per_pulse'])
np.testing.assert_array_equal(new['optics']['dataset']['rx']['psf_pixel_fraction'],old['optics']['dataset']['rx']['psf_pixel_fraction'])
values=cfg.model_dump();values['tx']['tx_model']='super_gaussian';values['rx'].update(rx_model='super_gaussian_psf',psf_sigma_h_um=4,psf_sigma_v_um=10,psf_order_h=2,psf_order_v=4)
demo=SimulationConfig.for_experiment('system',values,a)
light,groups,info=project_illumination(demo,a,lambda *_:None,lambda:False)
view=optical_view(demo,a,info)
sample=run_system(demo,a,lambda *_:None,lambda:False)
assert all(np.isfinite(r['phase_ns']) for r in sample['records'])
from spad_lidar.configuration import read_yaml
from spad_lidar.curves import merge_config
from spad_lidar.experiments.columns import run_columns
column_values=merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{
    'system_targets':{'slot_count':4},'tx':{'tx_model':'super_gaussian'},
    'rx':{'rx_model':'super_gaussian_psf','psf_sigma_h_um':4,'psf_sigma_v_um':10}})
column_cfg=SimulationConfig.for_experiment('columns',column_values,a)
column=run_columns(column_cfg,a,lambda *_:None,lambda:False)
assert column['audit']['final_records']==len(column['records'])
report={'utc':datetime.now(timezone.utc).isoformat(),'historical_job':JOB,'historical_result_sha256':sha256(path.read_bytes()).hexdigest(),
 'original_configuration':old['configuration'],'migrated_configuration':new['configuration'],'provenance':new['provenance'],
 'checks':{'gaussian_records_exactly_preserved':True,'gaussian_signal_exactly_preserved':True,'gaussian_pixel_psf_exactly_preserved':True},
 'super_gaussian_example':{'configuration':demo.model_dump(),'budget':info['budget'],'psf_figure':view['parameter_figures']['psf'],
    'b_record_count':len(sample['records']),'b_audit':{k:v for k,v in sample['audit'].items() if k not in ('trace','source')}},
 'column_example':{'configuration':column_cfg.model_dump(),'record_count':len(column['records']),
    'energy_residual_j':column['photon_flow']['values']['energy_balance_residual_j']}}
Path(__file__).with_name('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':report['checks'],'example_tx_fraction_sum':info['budget']['tx_angular_coverage_fraction'],'example_energy_residual_j':info['budget']['energy_balance_residual_j']},indent=2))

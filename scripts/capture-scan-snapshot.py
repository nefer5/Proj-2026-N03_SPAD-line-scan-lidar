"""Capture C configurations, full arrays, point clouds and numerical A/B regressions."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import csv
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,frozen_yaml,yaml_snapshot
from spad_lidar.experiments.scanning import run_scan
from spad_lidar.experiments.spatial import run_system


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')


if __name__=='__main__':
    output=ROOT/'artifacts/scan-upgrade/final'
    output.mkdir(parents=True,exist_ok=True)
    snapshot=yaml_snapshot();save(output/'yaml-snapshot.json',snapshot)
    with frozen_yaml(snapshot):
        a=Algorithms.load()
        reference=json.loads((ROOT/'artifacts/scan-upgrade/baseline/b-fixtures.json').read_text(encoding='utf-8'))
        for mode,expected in reference.items():
            cfg=SimulationConfig.for_experiment('system',{'timing':{'laser_shots':3},'readout':{'readout_mode':mode}},a)
            r=run_system(cfg,a,lambda *x:None,lambda:False)
            for key,value in expected.items():
                assert (r['optics']['budget'] if key=='budget' else r[key])==value,(mode,key)
        cases={
            'default':{},
            'static':{'scan':{'trajectory':'static'}},
            'timing-errors':{'scan':{'laser_time_offset_ns':10,'laser_jitter_std_ns':1,'encoder_latency_ns':2000,'encoder_angle_offset_mrad':.2}},
            'phase-mismatch':{'scan':{'phase_offset_ns':250000}},
            'gradient-motion':{'scan':{'frame_count':2},'scene_motion':{'range_gradient_m_per_rad':50,'radial_velocity_m_s':10}},
            'fixed-rx':{'scan':{'rx_scan_scale':0},'optics':{'rx_angle_h_min_mrad':-30,'rx_angle_h_max_mrad':30}},
            'partial-gate':{'scan':{'trajectory':'static','frame_rate_hz':1e9/1500},'timing':{'gate_start_ns':1600,'gate_width_ns':2000}},
        }
        summaries={}
        for name,overrides in cases.items():
            cfg=SimulationConfig.for_experiment('scan',overrides,a)
            r=run_scan(cfg,a,lambda *x:None,lambda:False)
            save(output/f'{name}-config.json',{'schema_version':2,'kind':'scan','experiment':cfg.model_dump()})
            save(output/f'{name}-result.json',r)
            summaries[name]={'summary':r['scan']['summary'],'frame_budget':r['scan']['frame_budget'],
                             'photon_flow_values':r['photon_flow']['values'],'provenance':r['provenance']}
            if name=='default':
                fields=['frame','angle_bin','channel','x_m','y_m','z_m','raw_distance_m','reported_h_mrad','reported_v_mrad','status']
                with (output/'default-point-cloud.csv').open('w',encoding='utf-8',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(r['scan']['point_cloud'])
        save(output/'case-summaries.json',summaries)
    manifest={'utc':datetime.now(timezone.utc).isoformat(),'b_regression':'All 7 digital modes exactly match pre-C records, histograms, audits and budgets.',
              'files':{p.name:{'sha256':sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(output.glob('*')) if p.is_file() and p.suffix in ('.json','.csv') and p.name!='manifest.json'}}
    save(output/'manifest.json',manifest)
    print('Saved 7 complete scan cases, XYZ CSV and hashes; all B digital baselines remain exact.')

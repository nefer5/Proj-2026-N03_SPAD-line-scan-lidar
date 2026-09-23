"""Regenerate the explicitly synthetic B dataset and auditable review snapshots."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.experiments.spatial import optical_dataset,run_system,project_illumination


def save(path,value,pretty=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2 if pretty else None),encoding='utf-8')


if __name__=='__main__':
    output=ROOT/'artifacts/architecture-upgrade/stage-3'
    a=Algorithms.load();c=SimulationConfig.for_experiment('system',{},a)
    data=optical_dataset(c,a).model_dump()
    save(ROOT/'data/synthetic/spatial-example.json',data)
    result=run_system(c,a,lambda *x:None,lambda:False)
    save(output/'default-result.json',result)
    save(output/'default-config.json',{'schema_version':2,'kind':'system','experiment':c.model_dump()},True)
    cases={}
    for name,overrides in {
        'edge_offset_120_um':{'optics':{'rx_offset_x_um':120}},
        'zero_pde':{'device':{'dcr_cps_per_spad':0,'other_noise_cps_per_spad':0},
                    'spectral_inputs':{'pde':{'mode':'basic','basic':{'shape':'constant','amplitude':0}}}},
        'background_enabled':{'timing':{'laser_shots':1},'optics':{'solar_enabled':True,'solar_illuminance_lux':100,
                                                               'other_light_enabled':True,'other_light_scale':0.001}},
    }.items():
        cfg=SimulationConfig.for_experiment('system',overrides,a)
        run=run_system(cfg,a,lambda *x:None,lambda:False)
        cases[name]={'configuration':cfg.model_dump(),'budget':run['optics']['budget'],
                     'illumination':run['illumination'],'audit':run['audit'],'provenance':run['provenance']}
    save(output/'validation-cases.json',cases,True)
    files=[ROOT/'data/synthetic/spatial-example.json',*(output/name for name in ('default-result.json','default-config.json','validation-cases.json'))]
    save(output/'manifest.json',{'utc':datetime.now(timezone.utc).isoformat(),
                                'files':{str(p.relative_to(ROOT)):{'sha256':sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files}},True)
    print('Saved synthetic optical dataset, complete default result and 3 review cases.')

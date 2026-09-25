"""Single-run diagnosis of the user's explicit fully-reset initial condition.
Not a new default and not a simulation of repeated slots or reset duration.
"""
import cProfile,hashlib,json,pstats,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.configuration import Algorithms,frozen_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.experiments.spatial import project_illumination
from spad_lidar.experiments.lab import run_illumination
job='965250a72c614ded835a515dc8f7a91d'
p=json.loads((ROOT/'artifacts/runs'/job/'request.json').read_text(encoding='utf-8'))
with frozen_yaml(p['yaml']):
 a=Algorithms.from_snapshot(p['algorithms']).model_copy(update={'readout_warmup_cycles':0})
 cfg=SimulationConfig.for_experiment('system',p['experiment'],a)
 light,groups,optics=project_illumination(cfg,a,lambda *args:None,lambda:False)
 profile=cProfile.Profile();start=time.perf_counter()
 profile.enable();result=run_illumination(cfg,a,light,groups,lambda *args:None,lambda:False);profile.disable()
 elapsed=time.perf_counter()-start
 stats=pstats.Stats(profile)
 top=sorted(stats.stats.items(),key=lambda pair:pair[1][3],reverse=True)[:14]
 audit=result['audit'];config={'experiment':cfg.model_dump(),'algorithms':a.model_dump()}
 output={'utc':datetime.now(timezone.utc).isoformat(),'source_job':job,'configuration':config,
  'configuration_sha256':hashlib.sha256(json.dumps(config,sort_keys=True,allow_nan=False).encode()).hexdigest(),
  'note':'Diagnostic: one acquisition with fully recovered initial SPAD/TDC state and no prehistory. Profiling overhead is included in elapsed time. Does not validate a 20 us slot or implement hardware reset/accumulator resources.',
  'elapsed_seconds_with_profiler':elapsed,'shape':optics['array_shape'],'readout_channels':len(result['histogram']['counts']),
  'source':audit['source'],'final_records':audit['final_records'],
  'spad_dead_losses':audit['spad_dead_losses'],'tdc_dead_losses':audit['tdc_dead_losses'],'capacity_losses':audit['capacity_losses'],
  'histogram_record_sum':sum(sum(row) for row in result['histogram']['counts']),
  'profile_top':[{'file':key[0],'line':key[1],'function':key[2],'calls':value[1],'self_s':value[2],'cumulative_s':value[3]} for key,value in top]}
 (ROOT/'artifacts/readout-discussion/reset-initial-diagnostic.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print(json.dumps({k:v for k,v in output.items() if k not in ('configuration','source')},ensure_ascii=False))
 print(json.dumps({'expected_work':audit['source']['expected_work'],'sampled_candidates':audit['source']['sampled_candidates'],'event_limit':a.max_readout_events_per_run}))

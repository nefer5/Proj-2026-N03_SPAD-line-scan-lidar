import sys,time,json
from pathlib import Path
sys.path.insert(0,'src')
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.experiments.columns import run_columns
c=SimulationConfig.for_experiment('columns',read_yaml('defaults.yaml')['experiments']['scan_demo'])
t=time.monotonic();r=run_columns(c,Algorithms.load(),lambda *args:None,lambda:False)
Path('artifacts/c-implementation/default-quiet-result.json').write_text(json.dumps(r,ensure_ascii=False,allow_nan=False),encoding='utf8')
print(json.dumps({'seconds':time.monotonic()-t,'records':len(r['records']),'columns':len(r['column_scan']['columns']),'work':r['column_scan']['projection_work'],'hits':r['column_scan']['projection_cache_hits'],'summary':r['column_scan']['summary'],'energy':r['photon_flow']['values']['energy_balance_residual_j']},indent=2))
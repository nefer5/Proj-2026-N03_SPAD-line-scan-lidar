import sys,time,json
sys.path.insert(0,'src')
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.curves import merge_config
from spad_lidar.experiments.columns import run_columns
c=SimulationConfig.for_experiment('columns',merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{'system_targets':{'slot_count':4}}))
t=time.monotonic();r=run_columns(c,Algorithms.load(),lambda *args:None,lambda:False)
print(json.dumps({'seconds':time.monotonic()-t,'records':len(r['records']),'columns':len(r['column_scan']['columns']),'work':r['column_scan']['projection_work'],'hits':r['column_scan']['projection_cache_hits'],'summary':r['column_scan']['summary'],'energy':r['photon_flow']['values']['energy_balance_residual_j']},indent=2))
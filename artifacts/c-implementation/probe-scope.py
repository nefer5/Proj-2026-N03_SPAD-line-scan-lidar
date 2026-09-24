import sys,time,json
sys.path.insert(0,'src')
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.experiments.columns import run_columns
c=SimulationConfig.for_experiment('columns',{'acquisition':{'scope_mode':'columns','scope_first_column':7,'scope_column_count':2}})
t=time.monotonic();r=run_columns(c,Algorithms.load(),lambda *args:None,lambda:False)
print(json.dumps({'seconds':time.monotonic()-t,'records':len(r['records']),'measured':r['column_scan']['measured_column_ids'],'target_columns':c.system_targets.slot_count,'background':c.background.model_dump(),'expected':r['audit']['source']['expected_work'],'observed_ns':r['column_scan']['frame_budget']['observation_duration_ns']},indent=2))
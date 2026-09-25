"""Build readout explanation examples from a saved job and an explicit slot time.
This is a design snapshot, not new hardware simulation or defaults.
"""
import argparse,json,hashlib,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--job-id',required=True);parser.add_argument('--slot-us',type=float,required=True);args=parser.parse_args()
p=json.loads((ROOT/'artifacts/runs'/args.job_id/'request.json').read_text(encoding='utf-8'))
c=p['experiment'];t=c['acquisition'];slot=args.slot_us*1000
period=t['period_ns'];start=t['gate_start_ns'];width=t['gate_width_ns']
if not math.isfinite(slot) or slot<=0:raise ValueError('Slot duration must be finite and positive')
if period<width:raise ValueError('This explanation requires non-overlapping periodic gates')
fit=0 if slot<start+width else math.floor((slot-start-width)/period)+1
cases=[]
for label,n in [('当前配置',t['laser_shots']),('时长可容纳示例',fit)]:
 windows=[{'index':i,'trigger_ns':i*period,'open_ns':i*period+start,'close_ns':i*period+start+width} for i in range(n)]
 end=windows[-1]['close_ns'] if windows else 0
 cases.append({'label':label,'shots':n,'windows':windows,'last_gate_close_ns':end,'overrun_ns':max(0,end-slot),'remaining_ns':max(0,slot-end)})
diag=json.loads((ROOT/'artifacts/readout-discussion/reset-initial-diagnostic.json').read_text(encoding='utf-8'))
snapshot={'source_job':args.job_id,'slot_ns':slot,'gate_width_ns':width,'period_ns':period,'gate_start_ns':start,
 'reset_time_ns':None,'reset_placement':'between_slots','cases':cases,
 'readout_mode':c['readout']['readout_mode'],'hit_capacity_per_exposure':c['readout']['tdc_max_hits_per_cycle'],
 'spad_dead_time_ns':c['spad']['spad_dead_time_ns'],'tdc_dead_time_ns':c['readout']['tdc_dead_time_ns'],
 'trial_count':c['acquisition']['monte_carlo_trials'],'noise_trials':p['algorithms']['readout_expected_trials'],
 'probe':{'expected_candidates':diag['source']['expected_work'],'sampled_candidates':diag['source']['sampled_candidates'],
          'records':diag['final_records'],'elapsed_s':diag['elapsed_seconds_with_profiler'],'event_limit':p['algorithms']['max_readout_events_per_run']},
 'notice':'slot时长由用户显式指定；其余时序来自保存的失败任务。复位耗时待定，不据此计算绝对帧率。'}
out=ROOT/'web/prototypes/slot-readout';(out/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
html=out/'index.html'
if html.exists():
 s=html.read_text(encoding='utf-8')
 def fix(m):
  name=m[1];f=ROOT/'web'/name.removeprefix('/static/') if name.startswith('/static/') else out/name
  return name+'?v='+hashlib.sha256(f.read_bytes()).hexdigest()[:16]
 s=re.sub(r'([^"\s<>]+\.(?:js|css|json))(?:\?v=[a-f0-9]+)?(?=")',fix,s);html.write_text(s,encoding='utf-8')
print(json.dumps({'snapshot':str(out/'snapshot.json'),'cases':[{k:v for k,v in c.items() if k!='windows'} for c in cases]},ensure_ascii=False))

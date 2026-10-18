"""Compare complete bounded realizations and config/schema contracts before/after."""
from pathlib import Path
import gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,yaml_snapshot,parse_yaml,frozen_yaml,read_yaml
from spad_lidar.experiments.single_channel import simulate
from spad_lidar.experiments.lab import run_lab
from spad_lidar.experiments.spatial_analysis import run_system_analysis
from spad_lidar.experiments.columns import run_columns
from spad_lidar.system_budget import calculate_budget
from spad_lidar.curves import merge_config

def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k!='utc'}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return v.item()
    return v
def encode(v):return json.dumps(clean(v),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def collect():
    results={};noop=lambda *a:None;never=lambda:False
    for kind in ('a','spad','system','scan','columns','budget'):
        cfg=SimulationConfig() if kind=='a' else SimulationConfig.for_experiment(kind,{})
        results['live_config_'+kind]={'configuration':cfg.model_dump(),'schema':type(cfg).model_json_schema()}
    snap=yaml_snapshot();snap['defaults.yaml']=parse_yaml((ROOT/'tests/fixtures/numerical-reference-defaults.yaml').read_text(encoding='utf8'))
    with frozen_yaml(snap):
        a=Algorithms.load();sampled=a.model_copy(update={'b_noise_reference':'sampled_output_mean','readout_expected_trials':2})
        for mode in read_yaml('readout-modes.yaml'):
            cfg=SimulationConfig(readout_mode=mode,range_m=20,laser_shots=3,laser_prf_hz=1000000,
                gate_width_ns=700,tdc_bin_ps=500,monte_carlo_trials=2,readout_mean_trials=2,noise_mean_trials=2,
                H_binning=2,V_binning=2,spad_dead_time_ns=20,detection_enabled=False,dcr_cps_per_spad=10000)
            results['A_'+mode]=simulate(cfg,debug=True)
        cfg=SimulationConfig.for_experiment('spad',{'timing':{'laser_shots':3}})
        results['SPAD']=run_lab(cfg,a,noop,never)
        cfg=SimulationConfig.for_experiment('system',{'acquisition':{'laser_shots':3,'monte_carlo_trials':3}})
        results['B_candidate']=run_system_analysis(cfg,a,noop,never)
        results['B_sampled']=run_system_analysis(cfg,sampled,noop,never)
        base=merge_config(read_yaml('defaults.yaml')['experiments']['scan_demo'],{
            'system_targets':{'slot_count':3},'acquisition':{'trial_count':3,'noise_trial_count':2}})
        cfg=SimulationConfig.for_experiment('columns',base)
        results['C_repeated']=run_columns(cfg,a,noop,never)
        cfg=SimulationConfig.for_experiment('budget',{})
        results['budget']=calculate_budget(cfg,a)
    return {k:clean(v) for k,v in results.items()}

if len(sys.argv)>2:
    from spad_lidar import configuration
    configuration.CONFIG_DIR=Path(sys.argv[2]).resolve()
mode=sys.argv[1];values=collect();payload=encode(values)
if mode=='before':
    with gzip.open(OUT/'numerical-before.json.gz','wb') as f:f.write(payload)
    print(json.dumps({'saved_cases':len(values),'sha256':hashlib.sha256(payload).hexdigest()}))
elif mode=='after':
    with gzip.open(OUT/'numerical-before.json.gz','rb') as f:before=json.load(f)
    comparisons={k:encode(before[k])==encode(v) for k,v in values.items()}
    failed=[k for k,ok in comparisons.items() if not ok]
    if failed:
        with gzip.open(OUT/'numerical-after.json.gz','wb') as f:f.write(payload)
    receipt={'ok':not failed,'cases':comparisons,'excluded_fields':['utc'],'comparison':'exact canonical JSON equality; no numeric tolerance','sha256':hashlib.sha256(payload).hexdigest()}
    (OUT/'numerical-comparison.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt));sys.exit(bool(failed))
else:raise ValueError('Expected before or after')

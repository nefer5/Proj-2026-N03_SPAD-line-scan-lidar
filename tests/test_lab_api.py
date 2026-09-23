import json
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.configuration import Algorithms, yaml_snapshot, read_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.runtime.jobs import JobManager, worker, update
from spad_lidar.experiments.configuration import LabConfig

client = TestClient(app)


def test_lab_default_and_unknown_keys_and_cache_policy():
    r = client.get('/api/experiments/spad')
    assert r.status_code == 200
    config = r.json()['defaults']
    assert 'range_m' not in config and 'optics' not in config
    assert client.get('/spad').headers['cache-control'] == 'no-store'
    html = client.get('/spad').text
    assert '/static/shared/labs.js?v=' in html
    assert client.post('/api/experiments/spad/validate', json={'range_m':100}).status_code == 422
    assert client.post('/api/experiments/spad/validate', json={'illumination':{'spatial_mode':None}}).status_code == 422
    assert client.post('/api/experiments/spad/import', content='schema_version: 2\nschema_version: 2', headers={'Content-Type':'text/plain'}).status_code == 422
    envelope = {'schema_version':2,'kind':'spad','experiment':config}
    assert client.post('/api/experiments/spad/import', content=json.dumps(envelope), headers={'Content-Type':'text/plain'}).json() == config


def test_every_lab_parameter_has_unit_and_condition_help():
    cfg = SimulationConfig.for_experiment('spad',{}).model_dump()
    help = read_yaml('parameter-help.yaml')
    for group, values in cfg.items():
        if group=='spectral_inputs':
            continue  # Shared Curve catalog documents all nested spectral controls.
        for key in values if isinstance(values,dict) else [group]:
            path = group+'.'+key if isinstance(values,dict) else group
            meta = help['experiments'].get(path,help.get(key))
            assert meta and all(k in meta for k in ('label','unit','description')), path


def test_persistent_jobs_cancel_and_snapshot(tmp_path,monkeypatch):
    # Deterministic worker execution isolates persistence from OS process scheduling.
    class Future:
        def add_done_callback(self,callback): pass
    class Pool:
        def submit(self,*args): return Future()
    m=JobManager(tmp_path);m.pool=Pool()
    job=m.submit('spad',{'timing':{'laser_shots':3}})
    payload=json.loads((tmp_path/job['id']/'request.json').read_text(encoding='utf-8'))
    assert payload['experiment']['timing']['laser_shots']==3
    worker(str(tmp_path),job['id'],'spad',payload['experiment'],payload['algorithms'],payload['yaml'])
    assert m.get(job['id'])['status']=='completed'
    result=m.result(job['id'])
    assert result['provenance']['rng_seed']==payload['experiment']['rng_seed']
    assert JobManager(tmp_path).result(job['id'])==result
    job=m.submit('spad',{});m.cancel(job['id'])
    p=json.loads((tmp_path/job['id']/'request.json').read_text(encoding='utf-8'))
    worker(str(tmp_path),job['id'],'spad',p['experiment'],p['algorithms'],p['yaml'])
    assert m.get(job['id'])['status']=='cancelled'
    import spad_lidar.webapi.labs as api
    monkeypatch.setattr(api,'manager',lambda:m)
    completed=m.list()[-1]['id']
    original=m.result(completed)['record_schema']['tdc_bin_ps']
    replay=client.post(f'/api/jobs/{completed}/replay',json={'bin_ps':original*2})
    assert replay.status_code==200
    assert sum(map(sum,replay.json()['counts']))==len(m.result(completed)['records'])
    assert client.post(f'/api/jobs/{completed}/replay',json={'bin_ps':original/2}).status_code==422


def test_opening_another_server_does_not_interrupt_a_live_owner(tmp_path):
    class Future:
        def add_done_callback(self,callback): pass
    class Pool:
        def submit(self,*args): return Future()
    m=JobManager(tmp_path);m.pool=Pool();job=m.submit('spad',{})
    assert JobManager(tmp_path).get(job['id'])['status']=='queued'
    update(tmp_path,job['id'],owner_pid=0)
    assert JobManager(tmp_path).get(job['id'])['status']=='interrupted'
    update(tmp_path,job['id'],preserve_interrupted=True,status='completed')
    assert m.get(job['id'])['status']=='interrupted'

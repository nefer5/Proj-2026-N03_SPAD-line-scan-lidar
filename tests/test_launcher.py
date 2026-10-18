from pathlib import Path
import os
import pytest
from fastapi.testclient import TestClient
from spad_lidar.api import app, ROOT
from spad_lidar.runtime.launcher import Process, select_roots, descendants, command_port

ROOT_PATH=Path(__file__).resolve().parents[1]

def proc(pid,parent,started,*argv):
    return Process(pid,parent,started,'python.exe',argv)


def test_runtime_identity_reports_actual_project_and_process():
    response=TestClient(app).get('/api/runtime')
    assert response.status_code==200
    data=response.json()
    assert Path(data['project_root'])==ROOT.resolve()
    assert data['server_pid']==os.getpid()
    assert data['software_version']==app.version
    assert response.headers['cache-control']=='no-store'


def test_verified_legacy_relative_launcher_includes_reload_and_pool_children():
    p=proc(10,1,100,'python','run.py','--reload','--open')
    server=proc(11,10,110,'python','-c','spawn_main')
    worker=proc(12,11,120,'python','-c','spawn_main')
    unrelated=proc(20,1,80,'python','other.py')
    snapshot={x.pid:x for x in [p,server,worker,unrelated]}
    roots=select_roots(ROOT_PATH,8016,8016,snapshot,True,{10},
        {'project_root':str(ROOT_PATH),'server_pid':11},None,999)
    assert [p.pid for p in roots]==[10]
    assert set(descendants(roots,snapshot))=={10,11,12}


def test_foreign_port_and_same_app_in_another_checkout_are_not_stopped():
    process=proc(10,1,100,'python','run.py','--port','8016')
    for runtime in [None,{'project_root':str(ROOT_PATH.parent/'other-project'),'server_pid':10}]:
        with pytest.raises(RuntimeError,match='unverified'):
            select_roots(ROOT_PATH,8016,8016,{10:process},True,{10},runtime,None,999)


def test_reused_pid_record_does_not_authorize_stopping_new_process():
    process=proc(10,1,200,'python','unrelated.py')
    record={'project_root':str(ROOT_PATH),'port':8016,'launcher_pid':10,'launcher_started':100}
    assert select_roots(ROOT_PATH,8016,8016,{10:process},False,set(),None,record,999)==[]


def test_scoped_orphan_launcher_can_be_found_without_a_listening_socket():
    old=proc(10,1,100,'python',str(ROOT_PATH/'run.py'),'--port','8123')
    other_port=proc(11,1,100,'python',str(ROOT_PATH/'run.py'),'--port','8124')
    current=proc(999,1,200,'python',str(ROOT_PATH/'run.py'),'--port','8123')
    roots=select_roots(ROOT_PATH,8123,8016,{p.pid:p for p in [old,other_port,current]},False,set(),None,None,999)
    assert [p.pid for p in roots]==[10]


def test_unidentifiable_relative_orphan_blocks_start_instead_of_killing_it():
    process=proc(10,1,100,'python','run.py','--reload')
    with pytest.raises(RuntimeError,match='Unverified relative'):
        select_roots(ROOT_PATH,8016,8016,{10:process},False,set(),None,None,999)


def test_stale_parent_pid_is_not_accepted_as_service_ancestor():
    # PID 10 now refers to a newer, unrelated launcher.
    parent=proc(10,1,300,'python','run.py')
    service=proc(11,10,200,'python','-c','spawn_main')
    with pytest.raises(RuntimeError,match='unverified'):
        select_roots(ROOT_PATH,8016,8016,{10:parent,11:service},True,{10},
                     {'project_root':str(ROOT_PATH),'server_pid':11},None,999)


def test_port_parser_and_malformed_records():
    assert command_port(('python','run.py','--port=8123'),8016)==8123
    assert command_port(('python','run.py','--port','8124'),8016)==8124
    assert command_port(('python','run.py','--port','bad'),8016) is None
    assert select_roots(ROOT_PATH,8016,8016,{},False,set(),None,{'launcher_pid':{}},999)==[]


def test_a_script_path_appearing_only_as_data_is_not_launcher_ownership():
    process=proc(10,1,100,'python','-c','import time;time.sleep(60)',str(ROOT_PATH/'run.py'))
    assert select_roots(ROOT_PATH,8016,8016,{10:process},False,set(),None,None,999)==[]


@pytest.mark.skipif(os.name!='nt',reason='Windows process handle identity')
def test_native_termination_rejects_reused_identity_and_cleans_only_its_child():
    import subprocess,sys
    from dataclasses import replace
    from spad_lidar.runtime.launcher import child_process_info,terminate_verified
    command=[sys.executable,'-c','import time;time.sleep(60)']
    child=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)
    info=child_process_info(child,command)
    try:
        with pytest.raises(RuntimeError,match='reused'):
            terminate_verified(replace(info,started=info.started-10000000))
        assert child.poll() is None
    finally:
        assert terminate_verified(info)>0
        child.wait(timeout=10)


def test_project_api_in_an_unknown_shared_host_is_not_force_stopped():
    process=proc(10,1,100,'python','notebook.py')
    with pytest.raises(RuntimeError,match='shared process'):
        select_roots(ROOT_PATH,8016,8016,{10:process},True,{10},
            {'project_root':str(ROOT_PATH),'server_pid':10},None,999)


def test_other_checkout_launcher_is_not_attributed_by_basename():
    parent=proc(10,1,100,'python',str(ROOT_PATH.parent/'other'/'run.py'))
    server=proc(11,10,110,'python','-c','spawn_main')
    with pytest.raises(RuntimeError,match='shared process'):
        select_roots(ROOT_PATH,8016,8016,{10:parent,11:server},True,{10},
            {'project_root':str(ROOT_PATH),'server_pid':11},None,999)

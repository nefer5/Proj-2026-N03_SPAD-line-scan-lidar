"""Foreground Windows launcher with explicit, project-verified restart."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import time
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))
DEFAULT_PORT = 8016


def main():
    parser=argparse.ArgumentParser(description='Start the LiDAR modeling server',
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--reload',action='store_true',help='Reload when Python source changes')
    parser.add_argument('--open',action='store_true',dest='open_browser',help='Open browser after verified startup')
    parser.add_argument('--restart',action='store_true',help='Stop verified old project processes before starting')
    parser.add_argument('--stop',action='store_true',help='Stop verified project instances on this port and exit')
    parser.add_argument('--port',type=int,default=DEFAULT_PORT,help='Local HTTP port')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be between 1 and 65535')
    if os.name!='nt':
        parser.exit(1,'This verified one-click launcher requires Windows. Use python -m uvicorn spad_lidar.api:app on other platforms.\n')
    from spad_lidar.runtime.launcher import (StartupLock,identity,port_open,port_owners,
        process_snapshot,select_roots,stop_trees,read_record,write_record,same_path,child_process_info,ServerJob)
    from spad_lidar import __version__
    if not args.stop:
        # Fail before shutting down a working server if this Python lacks dependencies.
        try:
            import uvicorn
            import spad_lidar.api
            from spad_lidar.models import SimulationConfig
            SimulationConfig()
        except ImportError as exc:
            print(f'Missing dependency: {exc}. Install with this Python: python -m pip install -e .',flush=True)
            return 1
        except (ValueError,RuntimeError,OSError) as exc:
            print('Invalid project configuration: '+str(exc),file=sys.stderr,flush=True)
            return 1
    directory=ROOT/'artifacts'/'runtime';directory.mkdir(parents=True,exist_ok=True)
    record_path=directory/f'launcher-{args.port}.json'
    url=f'http://127.0.0.1:{args.port}'
    instance=uuid.uuid4().hex
    child=None;child_identity=None;server_job=None
    try:
        with StartupLock(directory/f'launcher-{args.port}.lock'):
            occupied=port_open(args.port)
            runtime=identity(url) if occupied else None
            if occupied and not args.restart and not args.stop:
                if runtime and same_path(runtime.get('project_root',''),ROOT):
                    print(f'Project server already running: {url}. Use --restart for a fresh process.',flush=True)
                    if args.open_browser:webbrowser.open(url)
                    return 0
                raise RuntimeError(f'Port {args.port} is occupied by an unverified service; no process was stopped.')
            snapshot=process_snapshot()
            roots=select_roots(ROOT,args.port,DEFAULT_PORT,snapshot,occupied,
                               port_owners(args.port) if occupied else set(),runtime,
                               read_record(record_path),os.getpid())
            if roots:
                stopped=stop_trees(roots)
                print('Stopped old project Python processes: '+', '.join(map(str,stopped)),flush=True)
            deadline=time.monotonic()+10
            while port_open(args.port) and time.monotonic()<deadline:time.sleep(.1)
            if port_open(args.port):raise RuntimeError('Old port has not been released; new server was not started.')
            remaining=select_roots(ROOT,args.port,DEFAULT_PORT,process_snapshot(),False,set(),None,None,os.getpid())
            if remaining:raise RuntimeError('A project launcher remains; new server was not started.')
            if args.stop:
                old_record=read_record(record_path)
                if old_record and old_record.get('project_root')==str(ROOT):
                    old_record['status']='stopped';write_record(record_path,old_record)
                print(f'No project server remains on port {args.port}.',flush=True)
                return 0
            current=process_snapshot()[os.getpid()]
            record={'project_root':str(ROOT),'port':args.port,'launcher_pid':os.getpid(),
                    'launcher_started':current.started,'instance_id':instance,'status':'starting'}
            write_record(record_path,record)
            command=[sys.executable,'-m','uvicorn','spad_lidar.api:app','--app-dir',str(ROOT/'src'),
                     '--host','127.0.0.1','--port',str(args.port)]
            if args.reload:command+=['--reload','--reload-dir',str(ROOT/'src')]
            environment=os.environ.copy();environment['SPAD_LIDAR_INSTANCE_ID']=instance
            print(f'Starting fresh LiDAR {__version__}: {url}',flush=True)
            server_job=ServerJob('Local\\SPAD-LiDAR-'+instance)
            record['job_name']=server_job.name;write_record(record_path,record)
            child=subprocess.Popen(command,cwd=str(ROOT),env=environment,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4)  # CREATE_SUSPENDED
            child_identity=child_process_info(child,command)
            server_job.assign_and_resume(child)
            record['server_root_pid']=child.pid;record['server_root_started']=child_identity.started
            write_record(record_path,record)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if child.poll() is not None:raise RuntimeError('Server process exited during startup; see log above.')
                runtime=identity(url)
                if runtime and runtime.get('instance_id')==instance and same_path(runtime.get('project_root',''),ROOT):
                    if runtime.get('software_version')!=__version__:raise RuntimeError('New server version does not match this checkout.')
                    record.update(status='ready',server_pid=runtime['server_pid'],software_version=__version__)
                    write_record(record_path,record)
                    break
                time.sleep(.25)
            else:raise RuntimeError('Fresh server health/identity check timed out.')
            print(f"Ready: server PID {runtime['server_pid']}, instance {instance[:8]}, version {__version__}",flush=True)
        # Release startup lock after readiness so the next click can restart us.
        if args.open_browser:webbrowser.open(url)
        print('Keep this console open. Ctrl+C stops this instance.',flush=True)
        return child.wait()
    except KeyboardInterrupt:
        return 0
    except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
        print('Startup failed: '+str(exc),file=sys.stderr,flush=True)
        return 1
    finally:
        if server_job is not None:
            server_job.close()
        if child_identity is not None:
            try:stop_trees([child_identity])
            except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
                print('Cleanup could not be confirmed: '+str(exc),file=sys.stderr,flush=True)
        elif child is not None:
            try:stop_trees([child_process_info(child,command)])
            except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
                print('Startup cleanup could not be confirmed: '+str(exc),file=sys.stderr,flush=True)
        record=read_record(record_path)
        if record and record.get('instance_id')==instance:
            record['status']='stopped';write_record(record_path,record)


if __name__=='__main__':
    sys.exit(main())

"""Project-scoped launcher ownership and Windows process-tree cleanup.

No process is stopped merely because it uses the configured port or Python.
PID creation times are checked on an opened process handle before termination.
"""
from dataclasses import dataclass
from pathlib import Path
import ctypes
import json
import os
import socket
import subprocess
import time
from urllib.request import ProxyHandler, build_opener

OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    started: int
    executable: str
    argv: tuple


def _powershell(script):
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);'+script],
        capture_output=True, encoding='utf-8', check=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout.strip() or 'null')


def split_command(command):
    if not command:
        return ()
    from ctypes import wintypes
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    count = ctypes.c_int()
    array = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not array:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return tuple(array[i] for i in range(count.value))
    finally:
        kernel.LocalFree(array)


def process_snapshot():
    if os.name != 'nt':
        raise RuntimeError('Verified launcher restart currently requires Windows.')
    rows = _powershell("@(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%' OR Name = 'uvicorn.exe'\" | ForEach-Object {"
        "[pscustomobject]@{pid=$_.ProcessId;parent=$_.ParentProcessId;"
        "started=$_.CreationDate.ToUniversalTime().ToFileTimeUtc().ToString();"
        "executable=$_.ExecutablePath;command=$_.CommandLine}}) | ConvertTo-Json -Compress")
    if isinstance(rows, dict):
        rows = [rows]
    return {int(r['pid']): Process(int(r['pid']), int(r['parent']), int(r['started']),
                                  r['executable'] or '', split_command(r['command'])) for r in rows or []}


def port_open(port):
    with socket.socket() as connection:
        connection.settimeout(.3)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def port_owners(port):
    rows = _powershell(f"@(Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | "
                       "Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress")
    return set(rows if isinstance(rows, list) else [] if rows is None else [rows])


def identity(url):
    try:
        with OPENER.open(url+'/api/runtime', timeout=1) as response:
            value = json.load(response)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def same_path(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def command_port(argv, default_port):
    for i, arg in enumerate(argv):
        if arg == '--port' and i+1 < len(argv):
            try:
                return int(argv[i+1])
            except ValueError:
                return None
        if arg.startswith('--port='):
            try:
                return int(arg.split('=', 1)[1])
            except ValueError:
                return None
    return default_port


def absolute_launcher(process, root, port, default_port):
    if command_port(process.argv, default_port) != port:
        return False
    script = root/'run.py'
    if len(process.argv)>1 and Path(process.argv[1]).is_absolute() and same_path(process.argv[1],script):
        return True
    uvicorn_command=(process.argv[1:3]==('-m','uvicorn') or
                     bool(process.argv) and Path(process.argv[0]).name.lower()=='uvicorn.exe')
    if not uvicorn_command or 'spad_lidar.api:app' not in process.argv or '--app-dir' not in process.argv:
        return False
    index=process.argv.index('--app-dir')
    return index+1<len(process.argv) and Path(process.argv[index+1]).is_absolute() and same_path(process.argv[index+1],root/'src')


def ancestors(pid, snapshot):
    chain = []
    while pid in snapshot and pid not in {p.pid for p in chain}:
        process = snapshot[pid]
        if chain and process.started > chain[-1].started:
            break  # A reused parent PID cannot establish ownership.
        chain.append(process)
        pid = process.parent
    return chain


def select_roots(root, port, default_port, snapshot, occupied, owners, runtime, record, current_pid):
    roots = {p.pid: p for p in snapshot.values()
             if p.pid != current_pid and absolute_launcher(p, root, port, default_port)}
    if (record and isinstance(record.get('project_root'), str) and record['project_root']
            and type(record.get('launcher_pid')) is int and type(record.get('launcher_started')) is int
            and same_path(record['project_root'], root) and record.get('port') == port):
        process = snapshot.get(record.get('launcher_pid'))
        if process and process.pid != current_pid and process.started == record.get('launcher_started'):
            roots[process.pid] = process
    verified = False
    if (runtime and isinstance(runtime.get('project_root'), str) and runtime['project_root']
            and type(runtime.get('server_pid')) is int and same_path(runtime['project_root'], root)):
        chain = ancestors(runtime.get('server_pid'), snapshot)
        chain_ids = {p.pid for p in chain}
        if chain and owners and owners <= chain_ids:
            # A legacy relative `run.py` is accepted ONLY on this verified service's ancestry.
            def project_script(p):
                if len(p.argv)<2:return False
                script=Path(p.argv[1])
                return same_path(script,root/'run.py') if script.is_absolute() else p.argv[1].lower()=='run.py'
            candidates=[p for p in chain if p.pid!=current_pid and (project_script(p) or p.pid in roots)]
            if candidates:
                chosen=candidates[-1]
            else:
                dedicated=[p for p in chain if p.pid in owners and 'spad_lidar.api:app' in p.argv]
                if not dedicated:
                    raise RuntimeError('Project API is hosted by an unverified shared process; no process was stopped.')
                chosen=dedicated[-1]
            roots[chosen.pid] = chosen
            verified = True
    tree = descendants(roots.values(), snapshot)
    if occupied and not verified and (not owners or not owners <= set(tree)):
        raise RuntimeError(f'Port {port} belongs to an unverified process. No process was stopped; use another port or close its owner.')
    # Relative, unregistered orphan launchers cannot be attributed safely to a checkout.
    ambiguous = [p for p in snapshot.values() if p.pid != current_pid and p.pid not in tree
                 and command_port(p.argv, default_port) == port
                 and any(arg.lower() == 'run.py' for arg in p.argv)]
    if ambiguous:
        raise RuntimeError('Unverified relative run.py launcher(s) remain: '+', '.join(str(p.pid) for p in ambiguous)+
                           '. Close those launchers once; the updated launcher records absolute identity.')
    return list(roots.values())


def descendants(roots, snapshot):
    result = {p.pid: p for p in roots}
    changed = True
    while changed:
        changed = False
        for p in snapshot.values():
            parent = result.get(p.parent)
            if p.pid not in result and parent and p.started >= parent.started:
                result[p.pid] = p
                changed = True
    return result


class ServerJob:
    """The server tree dies with its launcher, including orphaned pool workers.

    The browser is opened by the launcher outside this Windows Job Object.
    Child execution is suspended until assignment, so no descendant can escape.
    """
    def __init__(self, name):
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),
                      ('flags',wintypes.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),
                      ('active_limit',wintypes.DWORD),('affinity',ctypes.c_size_t),
                      ('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(n,ctypes.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                      ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype=wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=self.kernel.CreateJobObjectW(None,name)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=Extended();info.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.get_last_error();self.close();raise ctypes.WinError(error)
        self.name=name

    def assign_and_resume(self, child):
        from ctypes import wintypes
        if not self.kernel.AssignProcessToJobObject(self.handle,int(child._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        class ThreadEntry(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('tid',wintypes.DWORD),
                      ('pid',wintypes.DWORD),('base_priority',wintypes.LONG),('delta_priority',wintypes.LONG),('flags',wintypes.DWORD)]
        k=self.kernel
        k.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
        k.Thread32First.argtypes=[wintypes.HANDLE,ctypes.POINTER(ThreadEntry)]
        k.Thread32Next.argtypes=[wintypes.HANDLE,ctypes.POINTER(ThreadEntry)]
        k.OpenThread.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenThread.restype=wintypes.HANDLE
        k.ResumeThread.argtypes=[wintypes.HANDLE];k.ResumeThread.restype=wintypes.DWORD
        snapshot=k.CreateToolhelp32Snapshot(0x4,0)
        if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        entry=ThreadEntry();entry.size=ctypes.sizeof(entry);resumed=False
        try:
            ok=k.Thread32First(snapshot,ctypes.byref(entry))
            while ok:
                if entry.pid==child.pid:
                    thread=k.OpenThread(0x2,False,entry.tid)
                    if not thread:raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if k.ResumeThread(thread)==0xFFFFFFFF:raise ctypes.WinError(ctypes.get_last_error())
                        resumed=True
                    finally:k.CloseHandle(thread)
                ok=k.Thread32Next(snapshot,ctypes.byref(entry))
            if not resumed:raise RuntimeError('Could not resume the verified server child.')
        finally:k.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle);self.handle=None


def child_process_info(child, command):
    """The Popen handle pins this exact child, including during startup failure."""
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    values=[wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(int(child._handle),*(ctypes.byref(v) for v in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    created=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
    return Process(child.pid,os.getpid(),created,command[0],tuple(command))


def terminate_verified(process):
    """Return the exact exit FILETIME; never act on a replacement PID."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x00100000, False, process.pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # already gone
            return None
        raise ctypes.WinError(error)
    def times():
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        return [(v.dwHighDateTime << 32) | v.dwLowDateTime for v in values]
    try:
        created, exited, *_ = times()
        # WMI exposes microsecond precision, while the handle uses 100ns ticks.
        if created//10 != process.started//10:
            raise RuntimeError(f'PID {process.pid} was reused; refusing to stop it.')
        if not exited:
            if not kernel.TerminateProcess(handle, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            if kernel.WaitForSingleObject(handle, 10000) != 0:
                raise RuntimeError(f'PID {process.pid} did not exit.')
        return times()[1]
    finally:
        kernel.CloseHandle(handle)


def stop_trees(roots):
    pending = descendants(roots, process_snapshot())
    tracked=dict(pending)
    stopped = {}
    for _ in range(8):
        for process in list(pending.values()):
            exit_time = terminate_verified(process)
            if exit_time:
                stopped[process.pid] = (process, exit_time)
        snapshot = process_snapshot()
        unresolved=[p for p in snapshot.values() if p.parent in tracked and p.parent not in stopped
                    and p.started>=tracked[p.parent].started and p.pid not in stopped]
        if unresolved:
            raise RuntimeError('Cannot verify exit of old parent process; startup cancelled before leaving ambiguous child processes.')
        # Catch children created between the initial snapshot and parent termination.
        pending = {p.pid: p for p in snapshot.values() if p.parent in stopped and
                   stopped[p.parent][0].started <= p.started <= stopped[p.parent][1]}
        tracked.update(pending)
        if not pending:
            return list(stopped)
    raise RuntimeError('Project child processes are still exiting; startup was cancelled.')


def read_record(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_record(path, record):
    temporary = path.with_name(path.name+'.'+record['instance_id']+'.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class StartupLock:
    """Serialize cleanup/startup only; a later click may restart a healthy instance."""
    def __init__(self, path):
        self.path = path
        self.file = None

    def __enter__(self):
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('a+b')
        self.file.seek(0, 2)
        if not self.file.tell():
            self.file.write(b'0');self.file.flush()
        deadline = time.monotonic()+40
        while True:
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.file.close()
                    raise RuntimeError('Another launcher is still starting this project; try again after it finishes.')
                time.sleep(.1)

    def __exit__(self, *exc):
        import msvcrt
        self.file.seek(0)
        msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()

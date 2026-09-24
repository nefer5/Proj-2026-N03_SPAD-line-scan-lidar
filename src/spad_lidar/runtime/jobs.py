from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
import json
import multiprocessing
import sqlite3
import traceback
import os

from ..configuration import Algorithms, frozen_yaml, yaml_snapshot
from ..models import SimulationConfig

ROOT = Path(__file__).resolve().parents[3] / 'artifacts' / 'runs'


def connect(root):
    db = sqlite3.connect(Path(root)/'jobs.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    return db


def process_alive(pid):
    if not pid:
        return False
    if pid == os.getpid():
        return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of termination.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX-only existence check; never use this on Windows.
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def update(root, job_id, preserve_interrupted=False, **fields):
    with connect(root) as db:
        suffix=" AND status!='interrupted'" if preserve_interrupted else ''
        db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?'+suffix, [*fields.values(), job_id])


def worker(root, job_id, kind, config, algorithms, snapshot):
    def cancelled():
        with connect(root) as db:
            row = db.execute('SELECT cancel_requested,status FROM jobs WHERE id=?', (job_id,)).fetchone()
        return bool(row['cancel_requested']) or row['status']=='interrupted'

    def progress(done, total, message):
        update(root, job_id, preserve_interrupted=True, completed=done, total=total, message=message)

    try:
        if cancelled():
            raise InterruptedError('Cancelled while queued')
        update(root, job_id, preserve_interrupted=True, status='running', message='准备计算')
        with frozen_yaml(snapshot):
            a = Algorithms.model_validate(algorithms)
            if kind == 'a':
                from ..simulator import simulate
                result = simulate(SimulationConfig.model_validate(config), debug=True)
            else:
                cfg = SimulationConfig.for_experiment(kind, config, a)
                if kind == 'spad':
                    from ..experiments.lab import run_lab
                    result = run_lab(cfg, a, progress, cancelled)
                elif kind == 'scan':
                    from ..experiments.scanning import run_scan
                    result = run_scan(cfg, a, progress, cancelled)
                elif kind == 'columns':
                    from ..experiments.columns import run_columns
                    result = run_columns(cfg,a,progress,cancelled)
                else:
                    from ..experiments.spatial_analysis import run_system_analysis
                    result = run_system_analysis(cfg, a, progress, cancelled)
            if cancelled():
                raise InterruptedError('Cancellation requested; completed metrics are withheld')
        path = Path(root)/job_id/'result.json'
        path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        update(root, job_id, preserve_interrupted=True, status='completed', completed=1, total=1, message='计算完成', result_path=str(path))
    except InterruptedError as exc:
        update(root, job_id, preserve_interrupted=True, status='cancelled', message=str(exc))
    except Exception as exc:
        (Path(root)/job_id/'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        update(root, job_id, preserve_interrupted=True, status='failed', message=f'{type(exc).__name__}: {exc}')


class JobManager:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self.pool = None
        self.worker_count = None
        with connect(self.root) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, created TEXT NOT NULL, status TEXT NOT NULL,
                completed INTEGER NOT NULL, total INTEGER NOT NULL, message TEXT NOT NULL,
                cancel_requested INTEGER NOT NULL, result_path TEXT)''')
            columns={row[1] for row in db.execute('PRAGMA table_info(jobs)')}
            if 'owner_pid' not in columns:
                db.execute('ALTER TABLE jobs ADD COLUMN owner_pid INTEGER')
            for row in db.execute("SELECT id,owner_pid FROM jobs WHERE status IN ('queued','running')").fetchall():
                if not process_alive(row['owner_pid']):
                    db.execute("UPDATE jobs SET status='interrupted',message='原执行服务已停止；配置快照已保留，可重新提交' WHERE id=?", (row['id'],))

    def submit(self, kind, overrides):
        if kind not in ('a', 'spad', 'system', 'scan', 'columns'):
            raise ValueError('Unknown experiment kind')
        snapshot = yaml_snapshot()
        with frozen_yaml(snapshot):
            a = Algorithms.load()
            cfg = SimulationConfig.model_validate(overrides) if kind == 'a' else SimulationConfig.for_experiment(kind, overrides, a)
        with self.lock:
            with connect(self.root) as db:
                count = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
                if count >= a.max_pending_jobs:
                    raise ValueError('Task queue is full; cancel a task or wait')
                if self.pool is not None and self.worker_count is not None and self.worker_count != a.max_job_workers:
                    if count:
                        raise ValueError('Worker limit changed; wait for active jobs before applying the new limit')
                    self.pool.shutdown(wait=False)
                    self.pool = None
                job_id = uuid4().hex
                directory = self.root/job_id
                directory.mkdir()
                payload = {'kind': kind, 'experiment': cfg.model_dump(), 'algorithms': a.model_dump(), 'yaml': snapshot}
                (directory/'request.json').write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
                db.execute('INSERT INTO jobs (id,kind,created,status,completed,total,message,cancel_requested,result_path,owner_pid) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (job_id, kind, datetime.now(timezone.utc).isoformat(), 'queued', 0, 1, '等待执行', 0, None, os.getpid()))
            if self.pool is None:
                self.pool = ProcessPoolExecutor(max_workers=a.max_job_workers, mp_context=multiprocessing.get_context('spawn'))
                self.worker_count = a.max_job_workers
            future = self.pool.submit(worker, str(self.root), job_id, kind, cfg.model_dump(), a.model_dump(), snapshot)
            def on_done(f):
                error = f.exception()
                if error:
                    update(self.root, job_id, preserve_interrupted=True, status='failed', message=f'Worker failed: {error}')
            future.add_done_callback(on_done)
        return self.get(job_id)

    def get(self, job_id):
        with connect(self.root) as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown job')
        return dict(row)

    def list(self):
        with connect(self.root) as db:
            return [dict(row) for row in db.execute('SELECT * FROM jobs ORDER BY created DESC')]

    def cancel(self, job_id):
        row = self.get(job_id)
        if row['status'] in ('queued', 'running'):
            update(self.root, job_id, cancel_requested=1, message='已请求取消；正在到达安全分块边界')
        return self.get(job_id)

    def result(self, job_id):
        row = self.get(job_id)
        if row['status'] != 'completed':
            raise ValueError('Only completed jobs have a complete result')
        return json.loads(Path(row['result_path']).read_text(encoding='utf-8'))


_manager = None
_lock = Lock()


def manager():
    global _manager
    with _lock:
        if _manager is None:
            _manager = JobManager(ROOT)
    return _manager

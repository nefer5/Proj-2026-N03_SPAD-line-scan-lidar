from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
import json
import multiprocessing
import sqlite3
import traceback

from ..configuration import Algorithms, frozen_yaml, yaml_snapshot
from ..models import SimulationConfig

ROOT = Path(__file__).resolve().parents[3] / 'artifacts' / 'runs'


def connect(root):
    db = sqlite3.connect(Path(root)/'jobs.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    return db


def update(root, job_id, **fields):
    with connect(root) as db:
        db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?', [*fields.values(), job_id])


def worker(root, job_id, kind, config, algorithms, snapshot):
    def cancelled():
        with connect(root) as db:
            row = db.execute('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
        return bool(row['cancel_requested'])

    def progress(done, total, message):
        update(root, job_id, completed=done, total=total, message=message)

    try:
        if cancelled():
            raise InterruptedError('Cancelled while queued')
        update(root, job_id, status='running', message='准备计算')
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
                else:
                    from ..experiments.spatial import run_system
                    result = run_system(cfg, a, progress, cancelled)
            if cancelled():
                raise InterruptedError('Cancellation requested; completed metrics are withheld')
        path = Path(root)/job_id/'result.json'
        path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        update(root, job_id, status='completed', completed=1, total=1, message='计算完成', result_path=str(path))
    except InterruptedError as exc:
        update(root, job_id, status='cancelled', message=str(exc))
    except Exception as exc:
        (Path(root)/job_id/'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        update(root, job_id, status='failed', message=f'{type(exc).__name__}: {exc}')


class JobManager:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self.pool = None
        with connect(self.root) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, created TEXT NOT NULL, status TEXT NOT NULL,
                completed INTEGER NOT NULL, total INTEGER NOT NULL, message TEXT NOT NULL,
                cancel_requested INTEGER NOT NULL, result_path TEXT)''')
            db.execute("UPDATE jobs SET status='interrupted',message='服务重启；配置快照已保留，可重新提交' WHERE status IN ('queued','running')")

    def submit(self, kind, overrides):
        if kind not in ('a', 'spad', 'system'):
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
                job_id = uuid4().hex
                directory = self.root/job_id
                directory.mkdir()
                payload = {'kind': kind, 'experiment': cfg.model_dump(), 'algorithms': a.model_dump(), 'yaml': snapshot}
                (directory/'request.json').write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',
                           (job_id, kind, datetime.now(timezone.utc).isoformat(), 'queued', 0, 1, '等待执行', 0, None))
            if self.pool is None:
                self.pool = ProcessPoolExecutor(max_workers=a.max_job_workers, mp_context=multiprocessing.get_context('spawn'))
            future = self.pool.submit(worker, str(self.root), job_id, kind, cfg.model_dump(), a.model_dump(), snapshot)
            def on_done(f):
                error = f.exception()
                if error:
                    update(self.root, job_id, status='failed', message=f'Worker failed: {error}')
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

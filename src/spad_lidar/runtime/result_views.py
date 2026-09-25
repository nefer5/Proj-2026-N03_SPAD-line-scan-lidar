"""Bounded read-only raw-result cache for interactive B views.

Callers must not mutate returned dictionaries. Keys include file metadata so
replaced files cannot reuse stale records. Limits are loaded by the caller.
"""
from collections import OrderedDict
from pathlib import Path
from threading import RLock
import json

_cache=OrderedDict()
_lock=RLock()


def cached_result(manager,job_id,limit):
    row=manager.get(job_id)
    if row['status']!='completed':raise ValueError('Only completed jobs have a complete result')
    path=Path(row['result_path']);stat=path.stat();key=(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
    with _lock:
        while len(_cache)>limit:_cache.popitem(last=False)
        if limit and key in _cache:
            _cache.move_to_end(key);return _cache[key]
        value=json.loads(path.read_text(encoding='utf-8'))
        if limit:
            _cache[key]=value
            while len(_cache)>limit:_cache.popitem(last=False)
        return value

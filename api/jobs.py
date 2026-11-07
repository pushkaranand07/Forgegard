"""
api/jobs.py — background analysis jobs
======================================
Web requests never run a model. They spool the upload to a shared directory,
enqueue a job and return; a separate worker process (`manage.py run_worker`)
loads the models once and runs jobs one at a time (audit I6, I11).

Backends (one code path, chosen by settings):
- ``sqlite`` (default): a queue file in FORGEGUARD_SPOOL_DIR. Runs anywhere,
  including Windows, with web and worker on the same host.
- ``redis``: FORGEGUARD_REDIS_URL. For docker-compose / multiple hosts.

Job and batch records live in the queue backend's key-value store, so web
and worker share them without a database. Records expire after
FORGEGUARD_JOB_TTL seconds.

Tests switch the queue to Huey's immediate mode, which runs a job
synchronously at enqueue time with in-memory storage.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from django.conf import settings
from huey import PriorityRedisHuey, SqliteHuey, crontab

from . import common

logger = logging.getLogger("forgeguard.jobs")

KINDS = ("image", "video", "unified")
QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
TERMINAL = (DONE, FAILED)
HEARTBEAT_KEY = "worker:heartbeat"
HEARTBEAT_INTERVAL = 10  # seconds

# Images take ~0.1 s, videos ~25 s on CPU: queue images first so one image never
# waits behind minutes of video (a running job is never interrupted).
IMAGE_PRIORITY, VIDEO_PRIORITY = 10, 0


class QueueFull(Exception):
    """The queue already holds FORGEGUARD_MAX_QUEUE jobs; the caller should get 503 BUSY."""


def _build_huey():
    backend = settings.FORGEGUARD_QUEUE_BACKEND
    if backend == "redis":
        # Priority-aware Redis storage (needs Redis >= 5); SQLite storage is priority-aware already
        return PriorityRedisHuey("forgeguard", url=settings.FORGEGUARD_REDIS_URL, results=True)
    os.makedirs(settings.FORGEGUARD_SPOOL_DIR, exist_ok=True)
    return SqliteHuey("forgeguard", filename=os.path.join(settings.FORGEGUARD_SPOOL_DIR, "queue.sqlite3"))


huey = _build_huey()


# ─────────────────────────────────────────────────────────────────────────────
# Records
# ─────────────────────────────────────────────────────────────────────────────

def _key(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def _save(key: str, record: Dict[str, Any]) -> None:
    # put() overwrites atomically on every backend (dict, Redis HSET, SQLite
    # INSERT OR REPLACE), so readers never see the record missing mid-update.
    huey.put(key, record)


def _load(key: str) -> Optional[Dict[str, Any]]:
    record = huey.get(key, peek=True)
    if record is None:
        return None
    if record.get("expires_at", float("inf")) < time.time():
        huey.delete(key)
        return None
    return record


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _load(_key("job", job_id))


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    return _load(_key("batch", batch_id))


def _update_job(job_id: str, **changes) -> None:
    record = get_job(job_id)
    if record is not None:
        record.update(changes)
        _save(_key("job", job_id), record)


def queue_depth() -> int:
    return huey.pending_count()


# ─────────────────────────────────────────────────────────────────────────────
# Submitting
# ─────────────────────────────────────────────────────────────────────────────

def _spool(upload) -> str:
    """Stream an upload into the shared spool directory (worker deletes it)."""
    spool = os.path.join(settings.FORGEGUARD_SPOOL_DIR, "uploads")
    os.makedirs(spool, exist_ok=True)
    ext = common.extension_of(upload.name)
    fd, path = tempfile.mkstemp(prefix="job_", suffix=f".{ext}" if ext else "", dir=spool)
    with os.fdopen(fd, "wb") as out:
        for chunk in upload.chunks():
            out.write(chunk)
    return path


def _keep_copy(upload) -> str:
    """FORGEGUARD_KEEP_UPLOADS: keep a copy of an analysed image (never served over HTTP)."""
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    name = f"uploaded_image_{int(time.time())}_{uuid.uuid4().hex[:8]}.{common.extension_of(upload.name)}"
    upload.seek(0)
    with open(os.path.join(settings.MEDIA_ROOT, name), "wb") as out:
        for chunk in upload.chunks():
            out.write(chunk)
    return name


def _new_job_record(job_id: str, kind: str, upload, path: str, batch_id: Optional[str], index: Optional[int]):
    now = time.time()
    return {
        "job_id": job_id,
        "kind": kind,
        "status": QUEUED,
        "file_name": upload.name,
        "path": path,
        "saved_name": _keep_copy(upload) if kind == "image" and settings.FORGEGUARD_KEEP_UPLOADS else None,
        "batch_id": batch_id,
        "file_index": index,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "http_status": None,
        "result": None,
        "expires_at": now + settings.FORGEGUARD_JOB_TTL,
    }


def priority_for(record: Dict[str, Any]) -> int:
    return IMAGE_PRIORITY if common.media_type_for(record["file_name"]) == "image" else VIDEO_PRIORITY


def _enqueue(record: Dict[str, Any]) -> None:
    _save(_key("job", record["job_id"]), record)
    try:
        run_job(record["job_id"], priority=priority_for(record))
    except Exception:
        # Could not reach the queue: undo so the upload is not orphaned
        _discard(record["path"])
        huey.delete(_key("job", record["job_id"]))
        raise


def submit(kind: str, upload) -> str:
    """Spool ``upload`` and enqueue one job. Raises QueueFull when the queue is full."""
    if kind not in KINDS:
        raise ValueError(f"unknown job kind {kind!r}")
    if queue_depth() >= settings.FORGEGUARD_MAX_QUEUE:
        raise QueueFull()
    job_id = uuid.uuid4().hex
    _enqueue(_new_job_record(job_id, kind, upload, _spool(upload), None, None))
    return job_id


def submit_batch(uploads: List[Any], rejected: List[Dict[str, Any]]) -> str:
    """Enqueue one unified job per upload under a batch id.

    ``rejected`` lists files that failed validation, reported with the batch.
    Raises QueueFull when the queue cannot take every file.
    """
    if queue_depth() + len(uploads) > settings.FORGEGUARD_MAX_QUEUE:
        raise QueueFull()
    batch_id = uuid.uuid4().hex
    now = time.time()
    jobs = []
    records = []
    for index, upload in uploads:
        job_id = uuid.uuid4().hex
        records.append(_new_job_record(job_id, "unified", upload, _spool(upload), batch_id, index))
        jobs.append({"job_id": job_id, "file_index": index, "file_name": upload.name})
    _save(_key("batch", batch_id), {
        "batch_id": batch_id,
        "jobs": jobs,
        "rejected": rejected,
        "created_at": now,
        "expires_at": now + settings.FORGEGUARD_JOB_TTL,
    })
    for record in records:
        _enqueue(record)
    return batch_id


# ─────────────────────────────────────────────────────────────────────────────
# Waiting (used by the synchronous compatibility endpoints)
# ─────────────────────────────────────────────────────────────────────────────

_waiters: Optional[threading.BoundedSemaphore] = None
_waiters_lock = threading.Lock()


def _waiter_slots() -> threading.BoundedSemaphore:
    global _waiters
    with _waiters_lock:
        if _waiters is None:
            _waiters = threading.BoundedSemaphore(max(0, settings.FORGEGUARD_MAX_SYNC_WAITERS) or 1)
        return _waiters


def wait_for(ids: List[str], timeout: float) -> bool:
    """Block until every job in ``ids`` is finished, up to ``timeout`` seconds.

    Only FORGEGUARD_MAX_SYNC_WAITERS requests may wait at once, so web threads
    stay free for other requests and health checks; the rest return at once.
    """
    if settings.FORGEGUARD_MAX_SYNC_WAITERS <= 0 or timeout <= 0:
        return all((get_job(i) or {}).get("status") in TERMINAL for i in ids)
    slots = _waiter_slots()
    if not slots.acquire(blocking=False):
        return all((get_job(i) or {}).get("status") in TERMINAL for i in ids)
    try:
        deadline = time.monotonic() + timeout
        delay = 0.05
        while True:
            if all((get_job(i) or {}).get("status") in TERMINAL for i in ids):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(delay)
            delay = min(delay * 1.5, 0.5)
    finally:
        slots.release()


# ─────────────────────────────────────────────────────────────────────────────
# Worker side
# ─────────────────────────────────────────────────────────────────────────────

def _discard(path: Optional[str]) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


@huey.task()
def run_job(job_id: str) -> None:
    from .analysis import RUNNERS

    record = get_job(job_id)
    if record is None:
        logger.warning("Job %s expired before it ran", job_id)
        return
    _update_job(job_id, status=RUNNING, started_at=time.time())
    try:
        runner = RUNNERS[record["kind"]]
        if record["kind"] == "image":
            status, body = runner(record["path"], record["file_name"], record.get("saved_name"))
        else:
            status, body = runner(record["path"], record["file_name"])
    except Exception:
        logger.exception("Job %s crashed", job_id)
        status, body = 500, common.error_response_body("Analysis failed due to a server error.")
    finally:
        _discard(record["path"])
    _update_job(
        job_id,
        status=DONE if status < 400 else FAILED,
        http_status=status,
        result=body,
        finished_at=time.time(),
    )


def write_heartbeat() -> None:
    """Record that a worker is alive, with what it has loaded (read by /api/health/)."""
    from core import model_registry
    from core.pipeline import image_processor, video_processor

    import torch

    cuda = torch.cuda.is_available()
    beat = {
        "ts": time.time(),
        "pid": os.getpid(),
        "device": "cuda" if cuda else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
        "models": {
            kind: {
                "loaded": loaded(path),
                "load_state": model_registry.load_state(path),
            }
            for kind, path, loaded in (
                ("image", common.image_model_path(), image_processor.is_model_loaded),
                ("video", common.video_model_path(), video_processor.is_model_loaded),
            )
        },
    }
    _save(HEARTBEAT_KEY, beat)


def read_heartbeat() -> Optional[Dict[str, Any]]:
    return huey.get(HEARTBEAT_KEY, peek=True)


def start_heartbeat() -> threading.Thread:
    def beat():
        while True:
            try:
                write_heartbeat()
            except Exception:
                logger.exception("Could not write worker heartbeat")
            time.sleep(HEARTBEAT_INTERVAL)

    thread = threading.Thread(target=beat, name="forgeguard-heartbeat", daemon=True)
    thread.start()
    return thread


def purge_expired() -> int:
    """Delete expired job/batch records and orphaned spool files. Returns files removed."""
    now = time.time()
    for key, raw in list(huey.storage.result_items().items()):
        name = key.decode() if isinstance(key, bytes) else key
        if not name.startswith(("job:", "batch:")):
            continue
        try:
            record = huey.serializer.deserialize(raw)
        except Exception:
            continue
        if isinstance(record, dict) and record.get("expires_at", float("inf")) < now:
            huey.delete(name)

    removed = 0
    spool = os.path.join(settings.FORGEGUARD_SPOOL_DIR, "uploads")
    if os.path.isdir(spool):
        for entry in os.scandir(spool):
            if entry.is_file() and entry.stat().st_mtime < now - settings.FORGEGUARD_JOB_TTL:
                _discard(entry.path)
                removed += 1
    return removed


@huey.periodic_task(crontab(minute="*/10"))
def purge_expired_periodically() -> None:
    purge_expired()

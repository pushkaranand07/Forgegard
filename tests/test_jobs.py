"""Background jobs (audit I6, I11): job/batch API, sync wrappers, admission, health, isolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from api import jobs
from core.pipeline.image_processor import ImageDetectionResult, InvalidImageError

from .conftest import HAS_WEIGHTS, WEIGHTS_DIR, make_image

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent


def _fake_result(label="AUTHENTIC"):
    return ImageDetectionResult(label=label, predicted_class=1 if label == "AUTHENTIC" else 0,
                                authentic_prob=0.9, tampered_prob=0.1, device="cpu")


# ── Job API ──────────────────────────────────────────────────────────────────

def test_job_is_accepted_then_polled_to_completion(client, fake_weights):
    with mock.patch("core.pipeline.image_processor.detect_image_bytes", return_value=_fake_result()):
        created = client.post("/api/jobs/", {"file": make_image()})
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "queued" and body["kind"] == "image"
    assert created["Location"] == body["poll"] == f"/api/jobs/{body['job_id']}/"

    polled = client.get(body["poll"]).json()
    assert polled["status"] == "done"
    assert polled["http_status"] == 200
    assert polled["result"]["label"] == "AUTHENTIC"


def test_failed_analysis_is_reported_on_the_job(client, fake_weights):
    with mock.patch("core.pipeline.image_processor.detect_image_bytes", side_effect=InvalidImageError("bad")):
        job_id = client.post("/api/jobs/", {"file": make_image()}).json()["job_id"]
    record = client.get(f"/api/jobs/{job_id}/").json()
    assert record["status"] == "failed"
    assert record["http_status"] == 400
    assert record["result"] == {"error": "bad", "status": "INVALID_IMAGE"}


def test_unknown_job_is_json_404(client):
    response = client.get("/api/jobs/doesnotexist/")
    assert response.status_code == 404
    assert response.json()["status"] == "NOT_FOUND"


@pytest.mark.parametrize("data,expected", [
    ({"file": SimpleUploadedFile("a.txt", b"x")}, "Unsupported file format"),
    ({"file": SimpleUploadedFile("a.jpg", b"x"), "kind": "video"}, "cannot be analysed as video"),
    ({"file": SimpleUploadedFile("a.jpg", b"x"), "kind": "bogus"}, "kind must be one of"),
    ({}, 'Use field name "file"'),
])
def test_job_submission_is_validated(client, data, expected):
    response = client.post("/api/jobs/", data)
    assert response.status_code == 400
    assert expected in response.json()["error"]


def test_expired_job_is_gone(client, fake_weights, settings):
    settings.FORGEGUARD_JOB_TTL = -1
    with mock.patch("core.pipeline.image_processor.detect_image_bytes", return_value=_fake_result()):
        job_id = client.post("/api/jobs/", {"file": make_image()}).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}/").status_code == 404


def test_purge_removes_expired_records_and_orphaned_uploads(settings, tmp_path):
    jobs._save("job:old", {"status": "done", "expires_at": time.time() - 1})
    jobs._save("job:new", {"status": "done", "expires_at": time.time() + 999})
    uploads = Path(settings.FORGEGUARD_SPOOL_DIR) / "uploads"
    uploads.mkdir(parents=True)
    orphan = uploads / "job_orphan.jpg"
    orphan.write_bytes(b"x")
    old = time.time() - settings.FORGEGUARD_JOB_TTL - 10
    os.utime(orphan, (old, old))
    fresh = uploads / "job_fresh.jpg"
    fresh.write_bytes(b"x")

    assert jobs.purge_expired() == 1
    assert jobs.huey.get("job:old", peek=True) is None
    assert jobs.huey.get("job:new", peek=True) is not None
    assert not orphan.exists() and fresh.exists()


@pytest.mark.parametrize("name,expected", [("a.jpg", jobs.IMAGE_PRIORITY), ("a.webp", jobs.IMAGE_PRIORITY),
                                           ("a.mp4", jobs.VIDEO_PRIORITY), ("a.gif", jobs.VIDEO_PRIORITY)])
def test_images_are_queued_ahead_of_videos(name, expected):
    assert jobs.priority_for({"file_name": name}) == expected
    assert jobs.IMAGE_PRIORITY > jobs.VIDEO_PRIORITY


def test_sqlite_queue_hands_out_image_jobs_before_waiting_videos(tmp_path):
    """The real SQLite storage (not immediate mode) must dequeue by priority."""
    from huey import SqliteHuey

    queue = SqliteHuey("prio-test", filename=str(tmp_path / "q.sqlite3"))

    @queue.task()
    def work(name):
        return name

    for name, prio in [("video-1", jobs.VIDEO_PRIORITY), ("video-2", jobs.VIDEO_PRIORITY),
                       ("image", jobs.IMAGE_PRIORITY)]:
        work(name, priority=prio)
    order = [queue.dequeue().args[0] for _ in range(3)]
    assert order == ["image", "video-1", "video-2"]


# ── Synchronous wrappers ─────────────────────────────────────────────────────

def test_wrapper_returns_202_with_job_when_the_job_outlasts_the_wait(client, fake_weights):
    with mock.patch("core.pipeline.image_processor.detect_image_bytes", return_value=_fake_result()), \
         mock.patch.object(jobs, "wait_for", return_value=False):
        response = client.post("/api/detect-image/", {"image": make_image()})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING" and body["poll"] == f"/api/jobs/{body['job_id']}/"
    assert client.get(body["poll"]).json()["result"]["label"] == "AUTHENTIC"


def test_waiter_cap_frees_threads_instead_of_blocking(settings):
    """When every wait slot is taken, a sync request must return at once (then 202), not block."""
    settings.FORGEGUARD_MAX_SYNC_WAITERS = 1
    jobs._save("job:slow", {"status": "running", "expires_at": time.time() + 60})
    slots = jobs._waiter_slots()
    assert slots.acquire(blocking=False)
    try:
        started = time.monotonic()
        assert jobs.wait_for(["slow"], timeout=5) is False
        assert time.monotonic() - started < 0.5
    finally:
        slots.release()


def test_wait_for_returns_when_jobs_finish(settings):
    jobs._save("job:a", {"status": "done", "expires_at": time.time() + 60})
    assert jobs.wait_for(["a"], timeout=5) is True


# ── Batches ──────────────────────────────────────────────────────────────────

def test_batch_api_reports_per_file_results(client, fake_weights):
    files = [make_image("one.jpg"), SimpleUploadedFile("notes.txt", b"x"), make_image("two.jpg")]
    with mock.patch("api.unified_detection.detect_image_bytes", return_value=_fake_result()):
        created = client.post("/api/batches/", {"file": files})
    assert created.status_code == 202
    body = created.json()
    assert [j["file_index"] for j in body["jobs"]] == [0, 2]
    assert body["rejected"][0]["file_index"] == 1

    summary = client.get(body["poll"]).json()
    assert summary["status"] == "partial_error"
    assert summary["done"] == summary["total"] == 2
    assert [r["file_name"] for r in summary["results"]] == ["one.jpg", "two.jpg"]
    assert summary["errors"][0]["file_name"] == "notes.txt"


def test_detect_batch_keeps_its_response_shape(client, fake_weights):
    files = [make_image("one.jpg"), make_image("two.jpg")]
    with mock.patch("api.unified_detection.detect_image_bytes", return_value=_fake_result()):
        response = client.post("/api/detect/batch", {"file": files})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success" and body["num_success"] == 2 and body["num_errors"] == 0
    assert {"results", "errors", "processing_time_ms"} <= set(body)


def test_detect_batch_returns_202_with_batch_when_it_outlasts_the_wait(client, fake_weights):
    with mock.patch("api.unified_detection.detect_image_bytes", return_value=_fake_result()), \
         mock.patch.object(jobs, "wait_for", return_value=False):
        response = client.post("/api/detect/batch", {"file": [make_image("a.jpg")]})
    assert response.status_code == 202
    poll = response.json()["poll"]
    assert poll.startswith("/api/batches/")
    assert client.get(poll).json()["status"] == "success"


# ── Readiness reflects the worker ────────────────────────────────────────────

@pytest.fixture
def as_worker_mode(monkeypatch):
    """Make health checks treat the queue as served by a separate worker process."""
    monkeypatch.setattr(jobs.huey, "_immediate", False)


def _beat(age: float = 0, loaded: bool = True) -> dict:
    state = {"state": "loaded" if loaded else "not_loaded", "error": None}
    return {"ts": time.time() - age, "pid": 1, "device": "cpu", "gpu_name": None,
            "models": {k: {"loaded": loaded, "load_state": state} for k in ("image", "video")}}


def test_health_is_degraded_without_a_worker(client, as_worker_mode, monkeypatch):
    monkeypatch.setattr(jobs, "read_heartbeat", lambda: None)
    body = client.get("/api/health/").json()
    assert body["status"] == "degraded"
    assert body["worker"]["alive"] is False


def test_health_is_degraded_when_the_worker_went_quiet(client, as_worker_mode, monkeypatch):
    monkeypatch.setattr(jobs, "read_heartbeat", lambda: _beat(age=120))
    assert client.get("/api/health/").json()["worker"]["alive"] is False


def test_health_is_degraded_when_the_queue_is_unreachable(client, as_worker_mode, monkeypatch):
    def down():
        raise ConnectionError("redis down")
    monkeypatch.setattr(jobs, "queue_depth", down)
    body = client.get("/api/health/").json()
    assert body["status"] == "degraded"
    assert body["worker"]["queue_reachable"] is False


@pytest.mark.skipif(not HAS_WEIGHTS, reason="model weights not present in weights/")
def test_health_is_ok_with_a_live_worker_and_verified_weights(client, as_worker_mode, monkeypatch, settings):
    settings.FORGEGUARD_WEIGHTS_DIR = WEIGHTS_DIR
    monkeypatch.setattr(jobs, "read_heartbeat", lambda: _beat(age=2))
    response = client.get("/api/health/")
    body = response.json()
    assert response.status_code == 200, body
    assert body["worker"]["alive"] is True and body["models"]["video"]["loaded"] is True


# ── Real processes: worker + web over the SQLite queue ───────────────────────

_WEB_CLIENT = textwrap.dedent(
    """
    import io, json, os, sys, time
    sys.path.insert(0, os.environ["FG_ROOT"])
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.test import Client
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (90, 140, 200)).save(buf, format="JPEG")
    client = Client()
    created = client.post("/api/jobs/", {"file": SimpleUploadedFile("photo.jpg", buf.getvalue())})
    job = created.json()
    deadline = time.time() + float(os.environ["FG_TIMEOUT"])
    while True:
        record = client.get(job["poll"]).json()
        if record["status"] in ("done", "failed") or time.time() > deadline:
            break
        time.sleep(0.2)
    live = client.get("/api/health/live")
    print(json.dumps({"created": created.status_code, "record": record, "live": live.status_code,
                      "torch_loaded_in_web": "torch" in sys.modules}))
    """
)


@pytest.mark.integration
def test_worker_process_runs_jobs_and_web_never_loads_torch(tmp_path):
    import torch

    from core.pipeline.image_processor import IMDModel

    weights = tmp_path / "weights"
    weights.mkdir()
    torch.save(IMDModel().state_dict(), weights / "model_c1.pth")  # tiny real checkpoint
    env = {**os.environ, "FG_ROOT": str(ROOT), "FG_TIMEOUT": "90",
           "FORGEGUARD_QUEUE_BACKEND": "sqlite", "FORGEGUARD_SPOOL_DIR": str(tmp_path / "spool"),
           "FORGEGUARD_WEIGHTS_DIR": str(weights), "FORGEGUARD_VERIFY_WEIGHTS": "false",
           "DJANGO_DEBUG": "true", "FORGEGUARD_RATE_LIMIT_PER_MINUTE": "0", "DJANGO_ALLOWED_HOSTS": "testserver"}

    worker = subprocess.Popen([sys.executable, str(ROOT / "manage.py"), "run_worker", "--no-warmup"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        script = tmp_path / "web_client.py"
        script.write_text(_WEB_CLIENT, encoding="utf-8")
        out = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=180)
        assert out.returncode == 0, out.stderr[-2000:]
        result = json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        worker.terminate()
        try:
            worker_log = worker.communicate(timeout=20)[0]
        except subprocess.TimeoutExpired:
            worker.kill()
            worker_log = worker.communicate()[0]

    assert result["created"] == 202
    assert result["record"]["status"] == "done", (result, worker_log[-2000:])
    # Tiny test model is not in the manifest, so it is unvalidated: a score, no verdict
    assert result["record"]["result"]["label"] == "UNVALIDATED"
    assert result["record"]["result"]["tampered_prob"] is not None
    assert result["live"] == 200
    assert result["torch_loaded_in_web"] is False
    assert list((tmp_path / "spool" / "uploads").iterdir()) == []

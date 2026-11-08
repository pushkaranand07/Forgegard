"""The worker side: warm-up, heartbeat, run_worker and worker_status (phase 5 coverage)."""

from __future__ import annotations

import threading
import time
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from api import jobs, warmup
from core import model_registry

# ── Warm-up ──────────────────────────────────────────────────────────────────

def test_warmup_loads_both_models_and_the_face_detector(settings, tmp_path):
    for name in ("model_c1.pth", "deepfake_detector_b7.pth"):
        (tmp_path / name).write_bytes(b"x")
    settings.FORGEGUARD_WEIGHTS_DIR = str(tmp_path)
    with mock.patch("core.pipeline.image_processor.load_model") as img, \
         mock.patch("core.pipeline.video_processor.load_model") as vid, \
         mock.patch("core.pipeline.video_processor.get_face_extractor") as faces:
        warmup.warmup()
    img.assert_called_once()
    vid.assert_called_once()
    faces.assert_called_once()


def test_warmup_skips_missing_weights_and_survives_failures(settings, tmp_path, caplog):
    (tmp_path / "deepfake_detector_b7.pth").write_bytes(b"x")  # image weights missing
    settings.FORGEGUARD_WEIGHTS_DIR = str(tmp_path)
    with mock.patch("core.pipeline.image_processor.load_model") as img, \
         mock.patch("core.pipeline.video_processor.load_model", side_effect=RuntimeError("bad")), \
         mock.patch("core.pipeline.video_processor.get_face_extractor", side_effect=RuntimeError("mtcnn")):
        warmup.warmup()  # must not raise
    img.assert_not_called()
    assert "weights not found" in caplog.text
    assert "Warm-up of the video model failed" in caplog.text
    assert "MTCNN face detector failed" in caplog.text


# ── Heartbeat ────────────────────────────────────────────────────────────────

def test_heartbeat_records_device_and_model_state(settings, tmp_path):
    settings.FORGEGUARD_WEIGHTS_DIR = str(tmp_path)
    model_registry.record_failed(str(tmp_path / "model_c1.pth"), RuntimeError("broken"))
    jobs.write_heartbeat()
    beat = jobs.read_heartbeat()
    assert time.time() - beat["ts"] < 5
    assert beat["device"] in ("cpu", "cuda")
    assert beat["models"]["image"]["load_state"]["state"] == "failed"
    assert beat["models"]["video"]["loaded"] is False


def test_heartbeat_thread_keeps_going_after_an_error(monkeypatch):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("redis blip")

    monkeypatch.setattr(jobs, "write_heartbeat", flaky)
    monkeypatch.setattr(jobs, "HEARTBEAT_INTERVAL", 0.01)
    stop = threading.Event()
    thread = jobs.start_heartbeat(stop)
    try:
        deadline = time.time() + 5
        while len(calls) < 3 and time.time() < deadline:
            time.sleep(0.01)
    finally:
        stop.set()  # never leak the thread into other tests
        thread.join(timeout=5)
    assert len(calls) >= 3
    assert not thread.is_alive()


# ── worker_status ────────────────────────────────────────────────────────────

def test_worker_status_passes_with_a_fresh_heartbeat(capsys):
    jobs._save(jobs.HEARTBEAT_KEY, {"ts": time.time(), "pid": 42, "device": "cpu"})
    call_command("worker_status")
    assert "worker alive (pid 42" in capsys.readouterr().out


@pytest.mark.parametrize("beat,message", [
    (None, "no worker heartbeat"),
    ({"ts": time.time() - 300, "pid": 1, "device": "cpu"}, "last worker heartbeat"),
])
def test_worker_status_fails_without_a_recent_heartbeat(beat, message):
    if beat:
        jobs._save(jobs.HEARTBEAT_KEY, beat)
    else:
        jobs.huey.delete(jobs.HEARTBEAT_KEY)
    with pytest.raises(CommandError, match=message):
        call_command("worker_status")


# ── run_worker ───────────────────────────────────────────────────────────────

def test_run_worker_refuses_in_immediate_mode(capsys):
    call_command("run_worker")  # tests run the queue in immediate mode
    assert "immediate mode" in capsys.readouterr().err


def test_run_worker_warms_up_beats_and_consumes(monkeypatch, settings):
    settings.FORGEGUARD_MAX_CONCURRENT_INFERENCES = 2
    monkeypatch.setattr(jobs.huey, "_immediate", False)
    consumer = mock.Mock()
    with mock.patch("api.warmup.warmup") as warm, \
         mock.patch.object(jobs, "start_heartbeat") as beat, \
         mock.patch.object(jobs.huey, "create_consumer", return_value=consumer) as create:
        call_command("run_worker")
    warm.assert_called_once()
    beat.assert_called_once()
    create.assert_called_once_with(workers=2, worker_type="thread", periodic=True)
    consumer.run.assert_called_once()


def test_run_worker_can_skip_warmup(monkeypatch):
    monkeypatch.setattr(jobs.huey, "_immediate", False)
    with mock.patch("api.warmup.warmup") as warm, mock.patch.object(jobs, "start_heartbeat"), \
         mock.patch.object(jobs.huey, "create_consumer", return_value=mock.Mock()):
        call_command("run_worker", "--no-warmup")
    warm.assert_not_called()

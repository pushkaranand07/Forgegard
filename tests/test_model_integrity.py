"""Fail-safe model loading: hash manifest, strict/safe loads, health, and API mapping."""

from __future__ import annotations

import os
from unittest import mock

import cv2
import numpy as np
import pytest
import torch
from django.core.files.uploadedfile import SimpleUploadedFile

from core import model_registry
from core.model_registry import CheckpointMismatchError, ModelUnavailableError, WeightsIntegrityError
from core.pipeline import image_processor, video_processor
from core.pipeline.image_processor import IMDModel

from .conftest import HAS_IMAGE_WEIGHTS, HAS_VIDEO_WEIGHTS, HAS_WEIGHTS, WEIGHTS_DIR, make_image

pytestmark = pytest.mark.django_db
needs_weights = pytest.mark.skipif(not HAS_WEIGHTS, reason="model weights not present in weights/")


@pytest.fixture(autouse=True)
def _fresh_caches():
    image_processor._MODEL_CACHE.clear()
    video_processor.invalidate_caches()
    yield
    image_processor._MODEL_CACHE.clear()
    video_processor.invalidate_caches()


# ── Manifest verification ────────────────────────────────────────────────────

def test_manifest_lists_both_served_models():
    files = model_registry.manifest()["models"]
    assert {"model_c1.pth", "deepfake_detector_b7.pth"} <= set(files)
    assert all(len(entry["sha256"]) == 64 for entry in files.values())


def test_tampered_manifest_file_is_rejected(tmp_path):
    path = tmp_path / "model_c1.pth"  # name is in the manifest, contents are not
    path.write_bytes(b"swapped weights")
    with pytest.raises(WeightsIntegrityError, match="does not match the manifest"):
        model_registry.verify_weights(str(path))


def test_verification_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGEGUARD_VERIFY_WEIGHTS", "false")
    path = tmp_path / "model_c1.pth"
    path.write_bytes(b"new checkpoint under evaluation")
    model_registry.verify_weights(str(path))  # no exception


def test_files_not_in_manifest_are_not_verified(tmp_path):
    path = tmp_path / "experiment.pth"
    path.write_bytes(b"anything")
    model_registry.verify_weights(str(path))


def test_hash_cache_notices_file_changes(tmp_path):
    path = tmp_path / "w.bin"
    path.write_bytes(b"a")
    first = model_registry.sha256_of(str(path))
    path.write_bytes(b"bb")
    assert model_registry.sha256_of(str(path)) != first


# ── Image loader ─────────────────────────────────────────────────────────────

def test_image_loader_rejects_hash_mismatch_and_records_failure(tmp_path):
    path = tmp_path / "model_c1.pth"
    torch.save(IMDModel().state_dict(), path)  # valid checkpoint, wrong hash
    with pytest.raises(WeightsIntegrityError):
        image_processor.load_model(str(path), torch.device("cpu"))
    assert model_registry.load_state(str(path))["state"] == "failed"


def test_image_loader_refuses_pickled_modules(tmp_path):
    path = tmp_path / "legacy.pth"
    torch.save(IMDModel(), path)  # whole-module pickle, needs unsafe unpickling
    with pytest.raises(ModelUnavailableError, match="convert_imd_to_state_dict"):
        image_processor.load_model(str(path), torch.device("cpu"))


def test_image_loader_rejects_architecture_mismatch(tmp_path):
    path = tmp_path / "other.pth"
    state = IMDModel().state_dict()
    state.pop("linear.4.bias")
    torch.save(state, path)
    with pytest.raises(CheckpointMismatchError, match=r"linear\.4\.bias"):
        image_processor.load_model(str(path), torch.device("cpu"))


def test_image_loader_accepts_matching_state_dict(tmp_path):
    path = tmp_path / "ok.pth"
    torch.save(IMDModel().state_dict(), path)
    model = image_processor.load_model(str(path), torch.device("cpu"))
    assert not model.training
    assert model_registry.load_state(str(path))["state"] == "loaded"


def test_image_model_outputs_logits_and_pipeline_returns_probabilities(tmp_path):
    path = tmp_path / "ok.pth"
    torch.save(IMDModel().state_dict(), path)
    result = image_processor.detect_image_bytes(make_image(size=(200, 160)).read(), str(path), torch.device("cpu"))
    assert result.authentic_prob + result.tampered_prob == pytest.approx(1.0, abs=1e-6)


# ── Video loader ─────────────────────────────────────────────────────────────

def test_corrupt_video_checkpoint_raises(tmp_path):
    path = tmp_path / "corrupt.pth"
    path.write_bytes(os.urandom(1024))
    with pytest.raises(ModelUnavailableError):
        video_processor.load_model(str(path), device="cpu")
    assert model_registry.load_state(str(path))["state"] == "failed"


def test_video_checkpoint_for_other_architecture_raises(tmp_path):
    path = tmp_path / "wrong_arch.pth"
    torch.save({"state_dict": {"module.fc.weight": torch.zeros(1, 4)}}, path)
    with pytest.raises(ModelUnavailableError):
        video_processor.load_model(str(path), encoder="tf_efficientnet_b4_ns", device="cpu")


def test_video_tampered_manifest_file_is_rejected_before_unpickling(tmp_path):
    path = tmp_path / "deepfake_detector_b7.pth"
    path.write_bytes(b"swapped")
    with mock.patch("torch.load") as torch_load, pytest.raises(WeightsIntegrityError):
        video_processor.load_model(str(path), device="cpu")
    torch_load.assert_not_called()


# ── Colour order and empty results ───────────────────────────────────────────

def _solid_video(path: str, bgr: tuple) -> str:
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for _ in range(10):
        writer.write(np.full((48, 64, 3), bgr, dtype=np.uint8))
    writer.release()
    return path


def test_frames_reach_face_detector_in_rgb_order(tmp_path, monkeypatch):
    """Fails if the BGR→RGB conversion is dropped or applied twice."""
    seen = []

    class _Recorder:
        def extract_face(self, frame):
            seen.append(frame)
            return None  # no face → UNSURE

    monkeypatch.setattr(video_processor, "load_model", lambda *a, **k: object())
    monkeypatch.setattr(video_processor, "get_face_extractor", lambda device: _Recorder())
    path = _solid_video(str(tmp_path / "blue.avi"), bgr=(255, 0, 0))  # pure blue in OpenCV's BGR

    result = video_processor.detect_video_file(path, "unused.pth", device="cpu", num_frames=4)

    assert seen, "no frames reached the face detector"
    r, g, b = (float(seen[0][..., i].mean()) for i in range(3))
    assert b > 200 and r < 50, f"expected blue in RGB order, got mean R={r:.0f} G={g:.0f} B={b:.0f}"
    assert result.label == "UNSURE"


def test_no_face_result_has_null_scores(tmp_path, monkeypatch):
    class _NoFace:
        def extract_face(self, frame):
            return None

    monkeypatch.setattr(video_processor, "load_model", lambda *a, **k: object())
    monkeypatch.setattr(video_processor, "get_face_extractor", lambda device: _NoFace())
    path = _solid_video(str(tmp_path / "grey.avi"), bgr=(128, 128, 128))
    result = video_processor.detect_video_file(path, "unused.pth", device="cpu", num_frames=4)
    assert result.label == "UNSURE"
    assert result.fake_prob is None and result.real_prob is None and result.confidence_pct is None


# ── API mapping ──────────────────────────────────────────────────────────────

def test_image_endpoint_maps_unavailable_model_to_503(client, fake_weights):
    integrity_error = WeightsIntegrityError("secret detail")
    with mock.patch("core.pipeline.image_processor.detect_image_bytes", side_effect=integrity_error):
        response = client.post("/api/detect-image/", {"image": make_image()})
    assert response.status_code == 503
    assert response.json()["status"] == "MODEL_UNAVAILABLE"
    assert "secret detail" not in response.content.decode()


def test_video_endpoint_maps_unavailable_model_to_503(client, fake_weights):
    with mock.patch("core.pipeline.video_processor.detect_video_file", side_effect=CheckpointMismatchError("x")):
        response = client.post("/api/detect-video/", {"video": SimpleUploadedFile("a.mp4", b"data")})
    assert response.status_code == 503
    assert response.json()["status"] == "MODEL_UNAVAILABLE"


def test_unified_endpoint_maps_unavailable_model_to_503(client, fake_weights):
    with mock.patch("api.unified_detection.detect_image_bytes", side_effect=ModelUnavailableError("x")):
        response = client.post("/api/detect/", {"file": make_image()})
    assert response.status_code == 503
    assert response.json()["label"] == "ERROR"


def test_image_response_carries_model_version_block(client, fake_weights):
    from .test_api import _fake_image_result

    with mock.patch("core.pipeline.image_processor.detect_image_bytes", return_value=_fake_image_result()):
        body = client.post("/api/detect-image/", {"image": make_image()}).json()
    assert set(body["model"]) == {"model_name", "weights_sha256", "pipeline_version"}
    assert body["model"]["pipeline_version"] == model_registry.pipeline_version()
    assert len(body["model"]["weights_sha256"]) == 12


# ── Health ───────────────────────────────────────────────────────────────────

def test_health_is_degraded_when_weights_fail_verification(client, fake_weights):
    response = client.get("/api/health/")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["models"]["image"]["present"] is True
    assert body["models"]["image"]["verified"] is False
    assert body["models"]["image"]["healthy"] is False


def test_health_is_degraded_after_a_failed_load(client, fake_weights, monkeypatch):
    monkeypatch.setenv("FORGEGUARD_VERIFY_WEIGHTS", "false")
    image_path = os.path.join(str(fake_weights), "model_c1.pth")
    model_registry.record_failed(image_path, CheckpointMismatchError("bad keys"))
    body = client.get("/api/health/").json()
    assert body["models"]["image"]["load_state"] == "failed"
    assert "bad keys" in body["models"]["image"]["load_error"]
    assert body["status"] == "degraded"


@needs_weights
def test_health_ok_with_real_verified_weights(client, settings):
    settings.FORGEGUARD_WEIGHTS_DIR = WEIGHTS_DIR
    body = client.get("/api/health/").json()
    assert body["status"] == "ok", body
    assert body["models"]["image"]["verified"] is True
    assert body["models"]["video"]["verified"] is True


@pytest.mark.skipif(not HAS_IMAGE_WEIGHTS, reason="model_c1.pth not present in weights/")
def test_real_image_weights_load_strictly_and_safely():
    image_processor.load_model(os.path.join(WEIGHTS_DIR, "model_c1.pth"), torch.device("cpu"))


@pytest.mark.skipif(not HAS_VIDEO_WEIGHTS, reason="deepfake_detector_b7.pth not present in weights/")
def test_real_video_weights_load_strictly_and_safely():
    video_processor.load_model(os.path.join(WEIGHTS_DIR, "deepfake_detector_b7.pth"), device="cpu")

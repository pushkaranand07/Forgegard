"""Pipeline units: image decoding guards, model caching, and real-weight smoke tests."""

from __future__ import annotations

import io
import os

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn

from core import model_registry
from core.model_registry import CheckpointMismatchError
from core.pipeline import image_processor, video_processor
from core.pipeline.image_processor import InvalidImageError

from .conftest import HAS_IMAGE_WEIGHTS, HAS_VIDEO_WEIGHTS, WEIGHTS_DIR


def _png(width: int, height: int, mode: str = "RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height)).save(buf, format="PNG")
    return buf.getvalue()


# ── Image decoding ───────────────────────────────────────────────────────────

def test_open_image_rejects_non_images():
    with pytest.raises(InvalidImageError, match="not a readable image"):
        image_processor._open_image(io.BytesIO(b"not an image"))


def test_open_image_rejects_truncated_files():
    data = _png(64, 64)
    with pytest.raises(InvalidImageError, match="corrupt or truncated"):
        image_processor._open_image(io.BytesIO(data[: len(data) // 2]))


def test_open_image_rejects_huge_dimensions():
    # 1-bit mode keeps the test file small while the pixel count is huge
    with pytest.raises(InvalidImageError, match="megapixels"):
        image_processor._open_image(io.BytesIO(_png(10_000, 6_000, mode="1")))


def test_open_image_accepts_normal_image():
    img = image_processor._open_image(io.BytesIO(_png(32, 32)))
    assert img.size == (32, 32)


# ── Video model cache ────────────────────────────────────────────────────────

class _TinyClassifier(nn.Module):
    def __init__(self, encoder: str = "tiny") -> None:
        super().__init__()
        self.fc = nn.Linear(4, 1)
        self.extra = nn.Linear(2, 2)


def _save_tiny(path, drop_prefix: str = "") -> str:
    """Save a _TinyClassifier checkpoint in the upstream format (DataParallel 'module.' keys)."""
    state = {k: v for k, v in _TinyClassifier().state_dict().items()
             if not (drop_prefix and k.startswith(drop_prefix))}
    torch.save({"epoch": 1, "state_dict": {f"module.{k}": v for k, v in state.items()}}, path)
    return str(path)


@pytest.fixture
def tiny_video_model(monkeypatch, tmp_path):
    monkeypatch.setattr(video_processor, "DeepFakeClassifier", _TinyClassifier)
    video_processor.invalidate_caches()
    yield _save_tiny(tmp_path / "tiny.pth")
    video_processor.invalidate_caches()


def test_video_model_is_cached_on_requested_device(tiny_video_model):
    first = video_processor.load_model(tiny_video_model, encoder="tiny", device="cpu")
    second = video_processor.load_model(tiny_video_model, encoder="tiny", device="cpu")
    assert first is second
    assert next(first.parameters()).device.type == "cpu"
    assert not first.training
    assert video_processor.is_model_loaded(tiny_video_model)


def test_video_checkpoint_with_missing_weights_raises(tiny_video_model, tmp_path):
    # Previously this only logged a warning and served partly random weights.
    partial = _save_tiny(tmp_path / "partial.pth", drop_prefix="extra.")
    with pytest.raises(CheckpointMismatchError, match=r"extra\.weight"):
        video_processor.load_model(partial, encoder="tiny", device="cpu")
    assert model_registry.load_state(partial)["state"] == "failed"
    assert not video_processor.is_model_loaded(partial)


def test_video_model_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        video_processor.load_model(str(tmp_path / "absent.pth"), device="cpu")


def test_confident_strategy_bounds():
    assert video_processor.confident_strategy([0.1, 0.2, 0.3]) == pytest.approx(0.2, abs=0.1)
    assert 0.0 <= video_processor.confident_strategy([0.99] * 20) <= 1.0


# ── Real weights (skipped in CI / when weights are absent) ───────────────────

needs_image_weights = pytest.mark.skipif(not HAS_IMAGE_WEIGHTS, reason="model_c1.pth not present in weights/")
needs_video_weights = pytest.mark.skipif(
    not HAS_VIDEO_WEIGHTS, reason="deepfake_detector_b7.pth not present in weights/"
)


@pytest.mark.models
@needs_image_weights
def test_image_model_end_to_end():
    buf = io.BytesIO()
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (256, 256, 3), dtype=np.uint8)).save(
        buf, format="JPEG", quality=92
    )
    result = image_processor.detect_image_bytes(buf.getvalue(), os.path.join(WEIGHTS_DIR, "model_c1.pth"))
    assert result.label == "UNVALIDATED"  # the deployed model is not validated (core/model_manifest.json)
    assert result.authentic_prob + result.tampered_prob == pytest.approx(1.0, abs=1e-3)


@pytest.mark.models
@needs_video_weights
def test_video_without_faces_is_unsure(tmp_path):
    import cv2

    path = str(tmp_path / "noface.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    for i in range(20):
        writer.write(np.full((120, 160, 3), i * 10, dtype=np.uint8))
    writer.release()

    result = video_processor.detect_video_file(
        path, os.path.join(WEIGHTS_DIR, "deepfake_detector_b7.pth"), device="cpu", num_frames=8,
    )
    assert result.label == "UNSURE"
    assert "NO_FACE_DETECTED" in result.notes

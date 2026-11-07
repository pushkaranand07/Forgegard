"""Shared fixtures. Nothing here needs a GPU, the network, or the real weights."""

from __future__ import annotations

import io
import os

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from api import common
from core import model_registry

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weights")
# Gated per model: CI can download the video checkpoint from upstream, but the
# image checkpoint has no public URL yet (see scripts/download_weights.py).
HAS_IMAGE_WEIGHTS = os.path.isfile(os.path.join(WEIGHTS_DIR, "model_c1.pth"))
HAS_VIDEO_WEIGHTS = os.path.isfile(os.path.join(WEIGHTS_DIR, "deepfake_detector_b7.pth"))
HAS_WEIGHTS = HAS_IMAGE_WEIGHTS and HAS_VIDEO_WEIGHTS


@pytest.fixture(autouse=True)
def _isolated(settings, tmp_path):
    """Fresh rate-limit counters, scratch dirs and inference slots per test."""
    settings.FORGEGUARD_TMP_DIR = str(tmp_path / "tmp")
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE = 0
    cache.clear()
    common._slots = None
    model_registry.reset_state()
    yield
    common._slots = None
    model_registry.reset_state()


@pytest.fixture
def fake_weights(settings, tmp_path):
    """A weights dir whose files exist (so endpoints get past the presence check)."""
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "model_c1.pth").write_bytes(b"not a real checkpoint")
    (weights / "deepfake_detector_b7.pth").write_bytes(b"not a real checkpoint")
    settings.FORGEGUARD_WEIGHTS_DIR = str(weights)
    return weights


@pytest.fixture
def empty_weights(settings, tmp_path):
    weights = tmp_path / "no-weights"
    weights.mkdir()
    settings.FORGEGUARD_WEIGHTS_DIR = str(weights)
    return weights


def make_image(name: str = "photo.jpg", size=(64, 64), fmt: str = "JPEG") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 80, 200)).save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")

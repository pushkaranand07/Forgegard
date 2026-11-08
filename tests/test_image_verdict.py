"""I2 / I16: the image endpoint never claims more than the model's evaluation supports.

- ELA only means something for JPEG compression, so PNG and WebP get UNSUPPORTED
  and the model is not even run.
- A model whose manifest entry is not "validated" returns UNVALIDATED: the raw
  score is reported as experimental, with no AUTHENTIC/TAMPERED verdict and no
  confidence figure.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest import mock

import pytest
import torch
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core import model_registry
from core.pipeline import image_processor
from core.pipeline.image_processor import IMDModel

pytestmark = pytest.mark.django_db


def _encode(fmt: str, size=(96, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 80, 200)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def tiny_model(tmp_path):
    path = tmp_path / "imd_tiny.pth"  # not in the manifest, so never "validated"
    torch.save(IMDModel().state_dict(), path)
    image_processor._MODEL_CACHE.clear()
    yield str(path)
    image_processor._MODEL_CACHE.clear()


# ── Pipeline ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("WEBP", "webp")])
def test_non_jpeg_is_unsupported_and_the_model_is_not_run(fmt, ext, tiny_model):
    with mock.patch.object(image_processor, "load_model", side_effect=AssertionError("model ran")):
        result = image_processor.detect_image_bytes(_encode(fmt), tiny_model, torch.device("cpu"), extension=ext)
    assert result.label == "UNSUPPORTED"
    assert result.tampered_prob is None and result.authentic_prob is None
    body = result.as_dict()
    assert body["confidence_pct"] is None and body["predicted_class"] == -1
    assert any("JPEG" in note for note in body["level1"]["notes"] + [body["reason"]])


def test_jpeg_from_an_unvalidated_model_gets_a_score_but_no_verdict(tiny_model):
    result = image_processor.detect_image_bytes(_encode("JPEG"), tiny_model, torch.device("cpu"), extension="jpg")
    body = result.as_dict()
    assert body["label"] == "UNVALIDATED"
    assert body["experimental"] is True
    assert body["predicted_class"] == -1
    assert body["confidence_pct"] is None
    assert body["tampered_prob"] + body["authentic_prob"] == pytest.approx(1.0, abs=1e-3)


def test_a_validated_model_gets_its_verdict_back(tiny_model, monkeypatch):
    monkeypatch.setattr(model_registry, "is_validated", lambda path: True)
    body = image_processor.detect_image_bytes(_encode("JPEG"), tiny_model, torch.device("cpu"),
                                              extension="jpg").as_dict()
    assert body["label"] in {"AUTHENTIC", "TAMPERED"}
    assert body["experimental"] is False
    assert body["predicted_class"] in {0, 1}
    assert 50 <= body["confidence_pct"] <= 100


def test_deployed_image_model_is_marked_unvalidated_in_the_manifest():
    entry = json.loads((Path(model_registry.MANIFEST_PATH)).read_text(encoding="utf-8"))["models"]["model_c1.pth"]
    assert entry["validated"] is False
    assert model_registry.is_validated("weights/model_c1.pth") is False


def test_models_missing_from_the_manifest_are_unvalidated():
    assert model_registry.is_validated("somewhere/experiment.pth") is False


# ── API ──────────────────────────────────────────────────────────────────────

def test_detect_image_reports_png_as_unsupported(client, fake_weights):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile("shot.png", _encode("PNG"))})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "UNSUPPORTED"
    assert body["tampered_prob"] is None and body["confidence_pct"] is None


def test_unified_endpoint_reports_png_as_unsupported(client, fake_weights):
    response = client.post("/api/detect/", {"file": SimpleUploadedFile("shot.png", _encode("PNG"))})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "UNSUPPORTED"
    assert body["confidence_pct"] is None
    assert body["level2"]["tampered_prob"] is None


def test_unified_endpoint_passes_the_experimental_flag_through(client, tiny_model, settings, tmp_path):
    weights = tmp_path / "w"
    weights.mkdir()
    (weights / "model_c1.pth").write_bytes(Path(tiny_model).read_bytes())
    (weights / "deepfake_detector_b7.pth").write_bytes(b"unused")
    settings.FORGEGUARD_WEIGHTS_DIR = str(weights)
    with mock.patch.object(model_registry, "verification_enabled", return_value=False):
        body = client.post("/api/detect/", {"file": SimpleUploadedFile("a.jpg", _encode("JPEG"))}).json()
    assert body["label"] == "UNVALIDATED"
    assert body["level2"]["experimental"] is True
    assert body["confidence_pct"] is None

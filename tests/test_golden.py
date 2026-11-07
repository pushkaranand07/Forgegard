"""
Golden-sample regression tests: the real models must reproduce recorded scores.

Expected values live in tests/golden/expected.json and are produced by
scripts/record_golden.py. A failure means the pipeline's numbers changed:
preprocessing, colour order, weights, library versions or aggregation.
Re-record only after an intentional change.

Skipped when the weights are absent (CI) or differ from the ones recorded.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest
import torch

from core.pipeline import image_processor, video_processor

from .conftest import WEIGHTS_DIR

GOLDEN = os.path.join(os.path.dirname(__file__), "golden")
EXPECTED_PATH = os.path.join(GOLDEN, "expected.json")

with open(EXPECTED_PATH, encoding="utf-8") as _f:
    EXPECTED = json.load(_f)

pytestmark = pytest.mark.models


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _weights(kind: str) -> str:
    return os.path.join(WEIGHTS_DIR, "model_c1.pth" if kind == "image" else "deepfake_detector_b7.pth")


@pytest.mark.parametrize("name", sorted(EXPECTED["samples"]))
def test_golden_sample(name):
    expected = EXPECTED["samples"][name]
    media = os.path.join(GOLDEN, "media", name)
    if not os.path.isfile(media):
        pytest.skip(f"golden media {name} not present")
    assert _sha256(media) == expected["media_sha256"], "fixture file changed; re-record deliberately"

    weights = _weights(expected["kind"])
    if not os.path.isfile(weights):
        pytest.skip(f"{os.path.basename(weights)} not present in weights/")
    if _sha256(weights) != expected["weights_sha256"]:
        pytest.skip("weights differ from the ones the golden values were recorded with")

    if expected["kind"] == "image":
        result = image_processor.detect_image_file(media, weights, torch.device("cpu"))
        score = result.tampered_prob
    else:
        result = video_processor.detect_video_file(media, weights, device="cpu")
        score = result.fake_prob

    assert result.label == expected["label"]
    if expected["score"] is None:
        assert score is None
    else:
        assert score == pytest.approx(expected["score"], abs=EXPECTED["tolerance"])


def test_golden_set_spans_the_score_range():
    """Guard against a golden set of only saturated scores, which would hide regressions."""
    scores = [s["score"] for s in EXPECTED["samples"].values() if s["score"] is not None]
    assert any(0.05 < s < 0.95 for s in scores)

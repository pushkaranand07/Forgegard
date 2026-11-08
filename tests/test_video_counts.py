"""I18: frames sampled and faces analysed are reported separately.

num_frames_processed meant "faces" for decided videos and "frames" for videos
with no face, and the UI showed it as "frames sampled". It is kept unchanged
for compatibility; num_frames_sampled and num_faces_analyzed say what they mean.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
from django.core.files.uploadedfile import SimpleUploadedFile
from torch import nn

from core.pipeline import video_processor as vp


def _video(path, frames=12):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 15, np.uint8))
    writer.release()
    return str(path)


class _FacesOnSome:
    """Finds a face on every other frame."""

    def __init__(self):
        self.n = 0

    def extract_face(self, frame):
        self.n += 1
        return frame[:32, :32] if self.n % 2 else None


class _Fake(nn.Module):
    def forward(self, x):
        return torch.full((x.shape[0], 1), 3.0)  # sigmoid ~0.95: confidently fake


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(vp, "get_face_extractor", lambda device: _FacesOnSome())
    monkeypatch.setattr(vp, "load_model", lambda *a, **k: _Fake())


def test_counts_distinguish_frames_from_faces(stubbed, tmp_path):
    result = vp.detect_video_file(_video(tmp_path / "v.avi"), "unused.pth", device="cpu", num_frames=10)
    assert result.num_frames_sampled == 10
    assert result.num_faces_analyzed == 5
    assert result.num_frames_processed == 5  # unchanged legacy meaning for decided videos


def test_counts_when_no_face_is_found(monkeypatch, tmp_path):
    class _None:
        def extract_face(self, frame):
            return None
    monkeypatch.setattr(vp, "get_face_extractor", lambda device: _None())
    monkeypatch.setattr(vp, "load_model", lambda *a, **k: object())
    result = vp.detect_video_file(_video(tmp_path / "v.avi"), "unused.pth", device="cpu", num_frames=8)
    assert (result.num_frames_sampled, result.num_faces_analyzed) == (8, 0)


@pytest.mark.django_db
def test_api_reports_both_counts(client, fake_weights, stubbed):
    data = Path(_video(fake_weights / "v.avi")).read_bytes()
    body = client.post("/api/detect-video/", {"video": SimpleUploadedFile("v.avi", data)}).json()
    # The service samples 32 frames; the stub finds a face on every other one
    assert body["num_frames_sampled"] == 32
    assert body["num_faces_analyzed"] == 16 == len(body["frame_predictions"])


@pytest.mark.django_db
def test_unified_endpoint_reports_both_counts(client, fake_weights, stubbed):
    data = Path(_video(fake_weights / "v.avi")).read_bytes()
    body = client.post("/api/detect/", {"file": SimpleUploadedFile("v.avi", data)}).json()
    assert body["num_faces_analyzed"] == len(body["frame_predictions"])
    assert body["num_frames_sampled"] >= body["num_faces_analyzed"]

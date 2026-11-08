"""I9: a failing face detector must not be reported as "no face found".

extract_face used to catch every exception and return None, and the shared
extractor was built with verbose=False, so an out-of-memory error or a bug
silently became an UNSURE "no face" result with nothing in the logs.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
import pytest

from core.pipeline import video_processor as vp


def _video(path, frames=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 20, np.uint8))
    writer.release()
    return str(path)


class _Detector:
    """Stands in for MTCNN: raises on the frames listed in `fail_on`, finds no face otherwise."""

    def __init__(self, fail_on):
        self.fail_on, self.calls = set(fail_on), 0

    def detect(self, img, landmarks=False):
        self.calls += 1
        if self.calls - 1 in self.fail_on:
            raise RuntimeError("detector exploded")
        return None, None


@pytest.fixture
def engine(monkeypatch):
    def make(fail_on):
        eng = vp.FaceDetectionEngine.__new__(vp.FaceDetectionEngine)
        eng.device, eng.verbose, eng.detector = "cpu", False, _Detector(fail_on)
        monkeypatch.setattr(vp, "get_face_extractor", lambda device: eng)
        monkeypatch.setattr(vp, "load_model", lambda *a, **k: object())
        return eng
    return make


def test_extract_face_propagates_detector_errors():
    eng = vp.FaceDetectionEngine.__new__(vp.FaceDetectionEngine)
    eng.device, eng.verbose, eng.detector = "cpu", False, _Detector(fail_on=[0])
    with pytest.raises(RuntimeError, match="detector exploded"):
        eng.extract_face(np.zeros((48, 64, 3), np.uint8))


def test_detector_failing_on_every_frame_fails_the_job(engine, tmp_path, caplog):
    engine(fail_on=range(100))
    with caplog.at_level(logging.ERROR, logger="forgeguard.video"), \
         pytest.raises(vp.FaceDetectionError, match="every sampled frame"):
        vp.detect_video_file(_video(tmp_path / "v.avi"), "unused.pth", device="cpu", num_frames=4)
    assert "detector exploded" in caplog.text


def test_detector_failing_on_some_frames_is_logged_and_noted(engine, tmp_path, caplog):
    engine(fail_on=[0, 2])
    with caplog.at_level(logging.ERROR, logger="forgeguard.video"):
        result = vp.detect_video_file(_video(tmp_path / "v.avi"), "unused.pth", device="cpu", num_frames=4)
    assert result.label == "UNSURE"
    assert "NO_FACE_DETECTED" in result.notes
    assert "FACE_DETECTION_ERRORS" in result.notes
    assert caplog.text.count("Face detection failed") == 2


def test_a_genuinely_faceless_video_has_no_error_note(engine, tmp_path):
    engine(fail_on=[])
    result = vp.detect_video_file(_video(tmp_path / "v.avi"), "unused.pth", device="cpu", num_frames=4)
    assert result.notes == ["NO_FACE_DETECTED"]


def test_api_maps_a_failed_detector_to_500(client, fake_weights, engine, db):
    from django.core.files.uploadedfile import SimpleUploadedFile

    engine(fail_on=range(100))
    data = open(_video(fake_weights / "v.avi"), "rb").read()
    response = client.post("/api/detect-video/", {"video": SimpleUploadedFile("v.avi", data)})
    assert response.status_code == 500
    assert "detector exploded" not in response.content.decode()

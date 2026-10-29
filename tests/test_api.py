"""HTTP-level behaviour of the detection API: validation, limits and error contract."""

from __future__ import annotations

import threading
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from api import common
from core.pipeline.image_processor import ImageDetectionResult

from .conftest import make_image

pytestmark = pytest.mark.django_db


def _fake_image_result() -> ImageDetectionResult:
    return ImageDetectionResult(
        label="AUTHENTIC", predicted_class=1, authentic_prob=0.9, tampered_prob=0.1,
        device="cpu", software_found=False, software_signature="", level1_notes=["No EXIF data found."],
    )


# ── Validation ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["/api/detect/", "/api/detect-image/", "/api/detect-video/", "/api/detect/batch"])
def test_post_without_file_is_400_json(client, url):
    response = client.post(url)
    assert response.status_code == 400
    assert response.json()["error"]
    assert response.json()["status"]


@pytest.mark.parametrize("url", ["/api/detect/", "/api/detect-image/", "/api/detect-video/"])
def test_get_is_405(client, url):
    assert client.get(url).status_code == 405


def test_unsupported_extension_is_rejected(client):
    upload = SimpleUploadedFile("notes.txt", b"hello")
    response = client.post("/api/detect/", {"file": upload})
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["error"]


def test_empty_file_is_rejected(client):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile("a.png", b"")})
    assert response.status_code == 400
    assert response.json()["error"] == "File is empty."


def test_upload_limit_comes_from_settings(client, settings):
    settings.FORGEGUARD_MAX_UPLOAD_MB = 1
    big = SimpleUploadedFile("big.png", b"0" * (1024 * 1024 + 1))
    response = client.post("/api/detect-image/", {"image": big})
    assert response.status_code == 400
    assert "1 MB" in response.json()["error"]


def test_oversized_request_is_413_before_parsing(client, settings):
    settings.FORGEGUARD_MAX_REQUEST_MB = 1
    response = client.post(
        "/api/detect/", data=b"x", content_type="application/octet-stream",
        CONTENT_LENGTH=str(2 * 1024 * 1024),
    )
    assert response.status_code == 413
    assert response.json()["status"] == "TOO_LARGE"


def test_batch_rejects_too_many_files(client, settings):
    settings.FORGEGUARD_MAX_BATCH_FILES = 2
    files = [make_image(f"{i}.jpg") for i in range(3)]
    response = client.post("/api/detect/batch", {"file": files})
    assert response.status_code == 400
    assert "at most 2" in response.json()["error"]


def test_undecodable_image_is_400_invalid_image(client, fake_weights):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile("x.jpg", b"definitely not a jpeg")})
    assert response.status_code == 400
    assert response.json()["status"] == "INVALID_IMAGE"


def test_unified_endpoint_reports_unreadable_media_as_422(client, fake_weights):
    response = client.post("/api/detect/", {"file": SimpleUploadedFile("x.png", b"garbage")})
    assert response.status_code == 422
    body = response.json()
    assert body["label"] == "ERROR"
    assert body["error"] == "The file is not a readable image."


# ── Model availability & server errors ───────────────────────────────────────

@pytest.mark.parametrize("url,field,name", [
    ("/api/detect-image/", "image", "a.jpg"),
    ("/api/detect-video/", "video", "a.mp4"),
])
def test_missing_weights_is_503_without_leaking_paths(client, empty_weights, url, field, name):
    response = client.post(url, {field: SimpleUploadedFile(name, b"data")})
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "model_not_found"
    assert str(empty_weights) not in response.content.decode()


def test_unexpected_failure_is_generic_500(client, fake_weights):
    with mock.patch("api.image_api.detect_image_bytes", side_effect=RuntimeError("secret internals")):
        response = client.post("/api/detect-image/", {"image": make_image()})
    assert response.status_code == 500
    assert "secret internals" not in response.content.decode()


def test_unhandled_exception_returns_json_with_request_id(client):
    with mock.patch("api.health_api.image_model_path", side_effect=RuntimeError("boom")):
        response = client.get("/api/health/")
    assert response.status_code == 500
    body = response.json()
    assert body["request_id"] == response["X-Request-ID"]
    assert "boom" not in response.content.decode()


# ── Success path (model mocked) ──────────────────────────────────────────────

def test_image_success_shape_and_uploads_not_kept(client, fake_weights, settings):
    settings.FORGEGUARD_KEEP_UPLOADS = False
    with mock.patch("api.image_api.detect_image_bytes", return_value=_fake_image_result()):
        response = client.post("/api/detect-image/", {"image": make_image()})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "AUTHENTIC"
    assert body["original_image"] is None
    assert body["processing_time_ms"] >= 0
    assert set(body["level1"]) == {"software_found", "software_signature", "notes"}


def test_image_upload_kept_when_enabled(client, fake_weights, settings, tmp_path):
    settings.FORGEGUARD_KEEP_UPLOADS = True
    with mock.patch("api.image_api.detect_image_bytes", return_value=_fake_image_result()):
        body = client.post("/api/detect-image/", {"image": make_image()}).json()
    assert (tmp_path / "media" / body["original_image"]).is_file()


def test_scratch_files_are_cleaned_up(client, fake_weights, settings, tmp_path):
    with mock.patch("api.unified_detection.detect_image_bytes", return_value=_fake_image_result()):
        response = client.post("/api/detect/", {"file": make_image()})
    assert response.status_code == 200
    assert list((tmp_path / "tmp").iterdir()) == []


# ── Rate limiting & concurrency ──────────────────────────────────────────────

def test_rate_limit_returns_429_with_retry_after(client, settings):
    settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE = 2
    codes = [client.post("/api/detect/").status_code for _ in range(3)]
    assert codes == [400, 400, 429]
    response = client.post("/api/detect/")
    assert response.json()["status"] == "RATE_LIMITED"
    assert 1 <= int(response["Retry-After"]) <= 60


def test_rate_limit_ignores_spoofed_forwarded_for_without_proxy(client, settings):
    settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE = 1
    settings.BEHIND_PROXY = False
    client.post("/api/detect/", HTTP_X_FORWARDED_FOR="1.1.1.1")
    response = client.post("/api/detect/", HTTP_X_FORWARDED_FOR="2.2.2.2")
    assert response.status_code == 429


def test_busy_server_returns_503(client, fake_weights, settings):
    settings.FORGEGUARD_MAX_CONCURRENT_INFERENCES = 1
    settings.FORGEGUARD_INFERENCE_QUEUE_TIMEOUT = 0
    holder_started, release = threading.Event(), threading.Event()

    def hold_slot():
        with common.inference_slot():
            holder_started.set()
            release.wait(5)

    thread = threading.Thread(target=hold_slot)
    thread.start()
    try:
        holder_started.wait(5)
        response = client.post("/api/detect-image/", {"image": make_image()})
    finally:
        release.set()
        thread.join()
    assert response.status_code == 503
    assert response.json()["status"] == "BUSY"
    assert response["Retry-After"]


# ── Health, routing, headers ─────────────────────────────────────────────────

def test_health_reports_limits_and_degraded_without_weights(client, empty_weights, settings):
    settings.FORGEGUARD_MAX_BATCH_FILES = 7
    response = client.get("/api/health/")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["limits"]["max_batch_files"] == 7
    assert "gif" in body["limits"]["video_extensions"]
    assert body["models"]["image"]["present"] is False


def test_liveness_probe(client):
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_path_is_json_404(client):
    response = client.get("/api/does-not-exist/")
    assert response.status_code == 404
    assert response.json()["status"] == "NOT_FOUND"


def test_request_id_is_echoed_or_generated(client):
    assert client.get("/api/health/live", HTTP_X_REQUEST_ID="abc-123")["X-Request-ID"] == "abc-123"
    generated = client.get("/api/health/live", HTTP_X_REQUEST_ID="bad id with spaces\n")["X-Request-ID"]
    assert generated and " " not in generated


def test_security_headers(client):
    response = client.get("/api/health/live")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"

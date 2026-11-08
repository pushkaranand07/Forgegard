"""I17: one error contract across every endpoint.

Every error body is {"error": <message>, "status": <legacy code>, "code": <ErrorCode>}.
"status" keeps its historical values so existing clients do not break; "code"
comes from one fixed set and means the same thing on every endpoint.
"""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from api import jobs
from api.errors import ErrorCode
from core.model_registry import WeightsIntegrityError

from .conftest import make_image

pytestmark = pytest.mark.django_db

CODES = {c.value for c in ErrorCode}

# (endpoint, field) pairs that analyse one file
SINGLE = [("/api/detect-image/", "image"), ("/api/detect/", "file"), ("/api/jobs/", "file")]


def _assert_error(response, status_code, code):
    assert response.status_code == status_code, response.content
    body = response.json()
    assert isinstance(body["error"], str) and body["error"]
    assert isinstance(body["status"], str) and body["status"]
    assert body["code"] == code, body
    assert body["code"] in CODES


@pytest.mark.parametrize("url,field", [*SINGLE, ("/api/detect-video/", "video"), ("/api/batches/", "file")])
def test_missing_file_is_invalid_input_everywhere(client, url, field):
    _assert_error(client.post(url), 400, ErrorCode.INVALID_INPUT)


@pytest.mark.parametrize("url,field", SINGLE)
def test_unsupported_extension_is_invalid_input_everywhere(client, url, field):
    _assert_error(client.post(url, {field: SimpleUploadedFile("a.txt", b"x")}), 400, ErrorCode.INVALID_INPUT)


@pytest.mark.parametrize("url,field", [("/api/detect-image/", "image"), ("/api/detect/", "file")])
def test_undecodable_image_is_invalid_media_everywhere(client, fake_weights, url, field):
    response = client.post(url, {field: SimpleUploadedFile("x.jpg", b"definitely not a jpeg")})
    assert response.json()["code"] == ErrorCode.INVALID_MEDIA
    assert response.status_code in (400, 422)  # legacy status codes kept per endpoint


@pytest.mark.parametrize("url,field", [("/api/detect-image/", "image"), ("/api/detect/", "file")])
def test_disguised_format_is_unsupported_media_everywhere(client, fake_weights, url, field):
    from .test_safe_image import _encode

    _assert_error(client.post(url, {field: SimpleUploadedFile("bmp.jpg", _encode("BMP"))}), 415,
                  ErrorCode.UNSUPPORTED_MEDIA)


@pytest.mark.parametrize("url,field", [("/api/detect-image/", "image"), ("/api/detect/", "file")])
def test_unavailable_model_is_model_unavailable_everywhere(client, fake_weights, url, field):
    target = "core.pipeline.image_processor.detect_image_bytes" if "image" in url else \
        "api.unified_detection.detect_image_bytes"
    with mock.patch(target, side_effect=WeightsIntegrityError("x")):
        _assert_error(client.post(url, {field: make_image()}), 503, ErrorCode.MODEL_UNAVAILABLE)


def test_missing_weights_is_model_unavailable(client, empty_weights):
    _assert_error(client.post("/api/detect-image/", {"image": make_image()}), 503, ErrorCode.MODEL_UNAVAILABLE)


@pytest.mark.parametrize("url,field", [("/api/detect-image/", "image"), ("/api/detect/", "file")])
def test_unexpected_failure_is_internal_error_everywhere(client, fake_weights, url, field):
    target = "core.pipeline.image_processor.detect_image_bytes" if "image" in url else \
        "api.unified_detection.detect_image_bytes"
    with mock.patch(target, side_effect=RuntimeError("secret")):
        response = client.post(url, {field: make_image()})
    _assert_error(response, 500, ErrorCode.INTERNAL_ERROR)
    assert "secret" not in response.content.decode()


@pytest.mark.parametrize("url,field", SINGLE)
def test_full_queue_is_busy_everywhere(client, fake_weights, settings, monkeypatch, url, field):
    settings.FORGEGUARD_MAX_QUEUE = 1
    monkeypatch.setattr(jobs, "queue_depth", lambda: 1)
    _assert_error(client.post(url, {field: make_image()}), 503, ErrorCode.BUSY)


def test_rate_limit_is_rate_limited(client, settings):
    settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE = 1
    client.post("/api/detect/")
    _assert_error(client.post("/api/detect/"), 429, ErrorCode.RATE_LIMITED)


def test_oversized_request_is_payload_too_large(client, settings):
    settings.FORGEGUARD_MAX_REQUEST_MB = 1
    response = client.post("/api/detect/", data=b"x", content_type="application/octet-stream",
                           CONTENT_LENGTH=str(2 * 1024 * 1024))
    _assert_error(response, 413, ErrorCode.PAYLOAD_TOO_LARGE)


@pytest.mark.parametrize("url", ["/api/does-not-exist/", "/api/jobs/unknown/", "/api/batches/unknown/"])
def test_unknown_resources_are_not_found(client, url):
    _assert_error(client.get(url), 404, ErrorCode.NOT_FOUND)


@pytest.mark.parametrize("method,url", [("get", "/api/detect-image/"), ("get", "/api/jobs/"),
                                        ("post", "/api/health/"), ("post", "/api/jobs/unknown/")])
def test_wrong_method_is_json_method_not_allowed(client, method, url):
    response = getattr(client, method)(url)
    _assert_error(response, 405, ErrorCode.METHOD_NOT_ALLOWED)
    assert response["Allow"]


def test_batch_errors_carry_codes(client, fake_weights):
    files = [SimpleUploadedFile("notes.txt", b"x"), SimpleUploadedFile("broken.jpg", b"not an image")]
    body = client.post("/api/detect/batch", {"file": files}).json()
    codes = {e["file_name"]: e["code"] for e in body["errors"]}
    assert codes == {"notes.txt": ErrorCode.INVALID_INPUT, "broken.jpg": ErrorCode.INVALID_MEDIA}


def test_error_code_set_is_closed():
    assert {"INVALID_INPUT", "INVALID_MEDIA", "UNSUPPORTED_MEDIA", "PAYLOAD_TOO_LARGE", "RATE_LIMITED",
                     "BUSY", "MODEL_UNAVAILABLE", "NOT_FOUND", "METHOD_NOT_ALLOWED", "INTERNAL_ERROR"} == CODES

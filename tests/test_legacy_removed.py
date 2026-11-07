"""I8/I10: the legacy template UI and its upload endpoints are gone, and no endpoint keeps uploads by default."""

from __future__ import annotations

import os
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from .conftest import make_image

pytestmark = pytest.mark.django_db

LEGACY_PATHS = ["/legacy/", "/legacy/photo/", "/legacy/photo-result/", "/legacy/about/",
                "/predict-image/", "/predict-video/"]


@pytest.mark.parametrize("path", LEGACY_PATHS)
@pytest.mark.parametrize("method", ["get", "post"])
def test_legacy_routes_are_404(client, path, method):
    response = getattr(client, method)(path)
    assert response.status_code == 404


def test_spa_is_read_only(client):
    assert client.get("/analyze").status_code in (200, 503)  # 503 when the UI is not built
    assert client.post("/analyze").status_code == 405


def test_non_api_404_does_not_need_templates(client):
    response = client.get("/static/does-not-exist.js")
    assert response.status_code == 404


def _all_files(root: str) -> list:
    if not os.path.isdir(root):
        return []
    return [os.path.join(d, f) for d, _, files in os.walk(root) for f in files]


@pytest.mark.parametrize("url,field,name,data", [
    ("/api/detect-image/", "image", "ok.jpg", None),
    ("/api/detect-image/", "image", "broken.jpg", b"not an image"),
    ("/api/detect/", "file", "ok.jpg", None),
    ("/api/detect/", "file", "broken.png", b"not an image"),
    ("/api/detect-video/", "video", "broken.mp4", b"not a video"),
    ("/api/detect/batch", "file", "broken.jpg", b"not an image"),
])
def test_no_upload_is_kept_by_default(client, fake_weights, settings, url, field, name, data):
    settings.FORGEGUARD_KEEP_UPLOADS = False
    upload = make_image(name) if data is None else SimpleUploadedFile(name, data)
    with mock.patch("core.pipeline.image_processor.load_model", side_effect=RuntimeError("no model in this test")):
        client.post(url, {field: upload})
    assert _all_files(settings.MEDIA_ROOT) == []
    assert _all_files(settings.FORGEGUARD_TMP_DIR) == []

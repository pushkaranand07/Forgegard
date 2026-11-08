"""Property-based tests: hostile bytes and names never crash validation or decoding.

Hypothesis generates arbitrary inputs, including near-valid image headers, and
checks that only the intended, typed errors come out (never a crash or a 500).
"""

from __future__ import annotations

import contextlib
import io
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from api import common
from core.pipeline.safe_image import InvalidImageError, UnsupportedMediaError, open_untrusted

# Real file signatures, so hypothesis also explores "looks like an image but is broken"
SIGNATURES = [b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF\x00\x00\x00\x00WEBP", b"BM", b"GIF89a",
              b"II*\x00", b"MM\x00*", b"8BPS", b""]
EXTENSIONS = ["jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "mp4", "", "JPG", "txt", "jpg.exe"]

hostile_bytes = st.builds(lambda sig, tail: sig + tail, st.sampled_from(SIGNATURES), st.binary(max_size=2048))


def _valid_image(fmt: str, w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format=fmt)
    return buf.getvalue()


@settings(max_examples=300, deadline=None)
@given(data=hostile_bytes, ext=st.sampled_from(EXTENSIONS))
def test_open_untrusted_only_raises_typed_errors(data, ext):
    try:
        img = open_untrusted(io.BytesIO(data), ext)
    except (InvalidImageError, UnsupportedMediaError):
        return
    assert img.format in ("JPEG", "PNG", "WEBP")  # anything that decodes is an allowed format


@settings(max_examples=100, deadline=None)
@given(fmt=st.sampled_from(["JPEG", "PNG", "WEBP"]), w=st.integers(1, 64), h=st.integers(1, 64),
       cut=st.integers(0, 4000))
def test_truncated_real_images_are_invalid_not_crashes(fmt, w, h, cut):
    data = _valid_image(fmt, w, h)
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
    with contextlib.suppress(InvalidImageError, UnsupportedMediaError):
        open_untrusted(io.BytesIO(data[: min(cut, len(data))]), ext)


@settings(max_examples=300, deadline=None)
@given(name=st.text(max_size=80), size=st.integers(-1, 10**10))
def test_upload_validation_never_raises(name, size):
    # A plain object: Django's own upload parser sanitises names before the app sees
    # them, so this checks the validator itself against any name and size.
    upload = SimpleNamespace(name=name, size=size)
    result = common.validate_upload(upload, common.IMAGE_EXTENSIONS | common.VIDEO_EXTENSIONS)
    assert result is None or isinstance(result, str)
    assert common.media_type_for(name) in (None, "image", "video")


@pytest.mark.django_db
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=hostile_bytes, ext=st.sampled_from(["jpg", "png", "webp"]))
def test_detect_image_never_returns_500(client, fake_weights, data, ext):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile(f"f.{ext}", data or b"\x00")})
    # 400 bad input, 415 other format, 503 the (fake) model cannot load; 200 only if it decoded
    assert response.status_code in (200, 400, 415, 503), response.content
    if response.status_code != 200:
        assert response.json()["code"]


# ── Regression: found by hypothesis on 2026-11-08 ────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize("cut", [3, 6, 12, 20])
def test_jpeg_truncated_inside_its_header_is_400_not_500(client, fake_weights, cut):
    """Pillow raised OSError while *opening* such files; it escaped and became a 500."""
    data = _valid_image("JPEG", 1, 1)[:cut]
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile("cut.jpg", data)})
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "INVALID_MEDIA"

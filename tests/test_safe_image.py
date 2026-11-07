"""I4: untrusted bytes only ever reach Pillow's JPEG, PNG and WebP decoders."""

from __future__ import annotations

import io
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import BmpImagePlugin, GifImagePlugin, Image, TiffImagePlugin

from core.pipeline import safe_image
from core.pipeline.image_processor import InvalidImageError
from core.pipeline.safe_image import UnsupportedMediaError, open_untrusted

pytestmark = pytest.mark.django_db


def _encode(fmt: str, size=(32, 24)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buf, format=fmt)
    return buf.getvalue()


# ── open_untrusted ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("fmt,ext", [("JPEG", "jpg"), ("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp")])
def test_allowed_formats_open_when_extension_matches(fmt, ext):
    img = open_untrusted(io.BytesIO(_encode(fmt)), ext)
    assert img.format == fmt
    assert img.size == (32, 24)


@pytest.mark.parametrize("fmt,ext", [("BMP", "jpg"), ("TIFF", "png"), ("GIF", "jpg"), ("TIFF", "jpg")])
def test_other_image_formats_are_unsupported_media(fmt, ext):
    with pytest.raises(UnsupportedMediaError):
        open_untrusted(io.BytesIO(_encode(fmt)), ext)


def test_disallowed_decoders_are_never_invoked():
    """The BMP/TIFF/GIF plugins must not even be asked to parse the bytes."""
    with mock.patch.object(BmpImagePlugin.BmpImageFile, "_open", side_effect=AssertionError("BMP parser ran")), \
         mock.patch.object(TiffImagePlugin.TiffImageFile, "_open", side_effect=AssertionError("TIFF parser ran")), \
         mock.patch.object(GifImagePlugin.GifImageFile, "_open", side_effect=AssertionError("GIF parser ran")):
        for fmt in ("BMP", "TIFF", "GIF"):
            with pytest.raises(UnsupportedMediaError):
                open_untrusted(io.BytesIO(_encode(fmt)), "jpg")


@pytest.mark.parametrize("fmt,ext", [("PNG", "jpg"), ("JPEG", "png"), ("WEBP", "jpeg")])
def test_allowed_format_with_mismatched_extension_is_unsupported(fmt, ext):
    with pytest.raises(UnsupportedMediaError, match="does not match"):
        open_untrusted(io.BytesIO(_encode(fmt)), ext)


def test_unknown_extension_is_unsupported():
    with pytest.raises(UnsupportedMediaError):
        open_untrusted(io.BytesIO(_encode("JPEG")), "bmp")


def test_garbage_is_invalid_not_unsupported():
    with pytest.raises(InvalidImageError, match="not a readable image"):
        open_untrusted(io.BytesIO(b"definitely not an image"), "jpg")


def test_unsupported_is_distinct_from_invalid():
    assert not issubclass(UnsupportedMediaError, InvalidImageError)


def test_pixel_cap_still_applies():
    buf = io.BytesIO()
    Image.new("1", (10_000, 6_000)).save(buf, format="PNG")
    with pytest.raises(InvalidImageError, match="megapixels"):
        open_untrusted(io.BytesIO(buf.getvalue()), "png")


def test_truncated_file_is_invalid():
    data = _encode("PNG", size=(64, 64))
    with pytest.raises(InvalidImageError, match="corrupt or truncated"):
        open_untrusted(io.BytesIO(data[: len(data) // 2]), "png")


def test_allow_list_is_exactly_jpeg_png_webp():
    assert set(safe_image.FORMAT_FOR_EXTENSION.values()) == {"JPEG", "PNG", "WEBP"}


# ── API mapping ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,fmt", [("bmp_as.jpg", "BMP"), ("tiff_as.png", "TIFF"), ("gif_as.jpg", "GIF"),
                                      ("png_as.jpg", "PNG")])
def test_detect_image_returns_415_for_disguised_formats(client, fake_weights, name, fmt):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile(name, _encode(fmt))})
    assert response.status_code == 415
    assert response.json()["status"] == "UNSUPPORTED_MEDIA"


def test_unified_endpoint_returns_415_for_disguised_formats(client, fake_weights):
    response = client.post("/api/detect/", {"file": SimpleUploadedFile("bmp_as.jpg", _encode("BMP"))})
    assert response.status_code == 415
    assert response.json()["label"] == "ERROR"


def test_batch_reports_disguised_format_per_file(client, fake_weights):
    response = client.post("/api/detect/batch", {"file": [SimpleUploadedFile("bmp_as.jpg", _encode("BMP"))]})
    errors = response.json()["errors"]
    assert len(errors) == 1 and "not supported" in errors[0]["error"]


@pytest.mark.parametrize("ext", ["bmp", "tif", "tiff"])
def test_dropped_extensions_are_rejected_before_decoding(client, ext):
    response = client.post("/api/detect-image/", {"image": SimpleUploadedFile(f"a.{ext}", b"data")})
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["error"]


def test_health_advertises_only_supported_image_types(client):
    assert client.get("/api/health/").json()["limits"]["image_extensions"] == ["jpeg", "jpg", "png", "webp"]

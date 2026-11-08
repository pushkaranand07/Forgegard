"""
core/pipeline/safe_image.py
===========================
The only place untrusted bytes are handed to Pillow.

Pillow picks a decoder from a file's *contents*, not its name, and ships decoders
for dozens of formats (BMP, TIFF, GIF, PSD, EPS, ...), several of which have had
memory-safety bugs. ``open_untrusted`` restricts Pillow to the JPEG, PNG and WebP
decoders, so no other decoder ever sees an upload. Recognisable images in any
other format, and files whose real format does not match their extension, raise
``UnsupportedMediaError`` (HTTP 415). Anything else unreadable raises
``InvalidImageError`` (HTTP 400).

Calling ``PIL.Image.open`` anywhere else is blocked by ruff (TID251).
"""

from __future__ import annotations

import os
from typing import BinaryIO

from PIL import Image

# Larger images are rejected before decoding: ELA holds several full-size copies.
MAX_IMAGE_PIXELS = 50_000_000

# Extension -> the only Pillow format allowed for it
FORMAT_FOR_EXTENSION = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
ALLOWED_FORMATS = tuple(sorted(set(FORMAT_FOR_EXTENSION.values())))

# Signatures of image formats we recognise but refuse to decode
_OTHER_IMAGE_SIGNATURES = (
    (b"BM", "BMP"),
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"8BPS", "PSD"),
    (b"\x00\x00\x01\x00", "ICO"),
    (b"\x00\x00\x00\x0cjP  ", "JPEG 2000"),
    (b"\xff\x4f\xff\x51", "JPEG 2000"),
    (b"%!PS", "EPS"),
    (b"\xc5\xd0\xd3\xc6", "EPS"),
    (b"qoif", "QOI"),
    (b"DDS ", "DDS"),
    (b"icns", "ICNS"),
)
_ISO_BMFF_IMAGE_BRANDS = (b"heic", b"heix", b"mif1", b"avif", b"avis")


class InvalidImageError(ValueError):
    """The upload is not a decodable image, or is too large to analyse safely."""


class UnsupportedMediaError(ValueError):
    """The upload is an image format ForgeGuard does not decode, or not the format its name says."""


def _recognised_other_format(head: bytes) -> str | None:
    for signature, name in _OTHER_IMAGE_SIGNATURES:
        if head.startswith(signature):
            return name
    if head[4:8] == b"ftyp" and head[8:12] in _ISO_BMFF_IMAGE_BRANDS:
        return "HEIF/AVIF"
    return None


def _open(fp: BinaryIO, extension: str | None) -> Image.Image:
    expected = None
    if extension is not None:
        expected = FORMAT_FOR_EXTENSION.get(extension.lower().lstrip("."))
        if expected is None:
            raise UnsupportedMediaError(f"'.{extension}' images are not supported. Use JPEG, PNG or WebP.")

    head = fp.read(16)
    fp.seek(0)
    try:
        img = Image.open(fp, formats=ALLOWED_FORMATS)  # noqa: TID251 — the one sanctioned call
    except Image.DecompressionBombError as exc:
        raise InvalidImageError("The image is too large to analyse.") from exc
    except Image.UnidentifiedImageError as exc:
        other = _recognised_other_format(head)
        if other:
            raise UnsupportedMediaError(f"{other} images are not supported. Use JPEG, PNG or WebP.") from exc
        raise InvalidImageError("The file is not a readable image.") from exc

    if expected is not None and img.format != expected:
        raise UnsupportedMediaError(
            f"The file is a {img.format} image, which does not match its .{extension} extension."
        )
    if img.width * img.height > MAX_IMAGE_PIXELS:
        raise InvalidImageError(
            f"Image is {img.width}×{img.height}; the maximum is {MAX_IMAGE_PIXELS // 1_000_000} megapixels."
        )
    try:
        img.load()  # surface truncated / corrupt files here rather than mid-pipeline
    except (OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError("The image file is corrupt or truncated.") from exc
    return img


def open_untrusted(source: str | os.PathLike | BinaryIO, extension: str | None = None) -> Image.Image:
    """Open and fully decode an untrusted image.

    ``extension`` is the upload's declared extension (``"jpg"``, ``".png"``, ...).
    When given, the decoded format must match it; API code always passes it. The
    decoder allow-list applies either way.
    """
    if isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as fp:
            return _open(fp, extension)
    return _open(source, extension)

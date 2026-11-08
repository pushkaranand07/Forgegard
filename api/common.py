"""
common.py — Shared plumbing for the detection endpoints
=======================================================
One place for the upload rules (extensions, size limits), the JSON error
shape and per-IP rate limiting. (Concurrency is bounded by the job queue,
see api/jobs.py.) Kept free of torch imports so middleware and
settings can load it cheaply.
"""

from __future__ import annotations

import functools
import os
import time
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


# Must match core.pipeline.safe_image.FORMAT_FOR_EXTENSION: only these decoders are ever run.
IMAGE_EXTENSIONS: frozenset = frozenset({"jpg", "jpeg", "png", "webp"})
# GIFs are treated as (animated) video: the frame model handles them, ELA does not.
VIDEO_EXTENSIONS: frozenset = frozenset({"mp4", "avi", "webm", "mov", "mkv", "flv", "3gp", "wmv", "gif"})


def extension_of(file_name: str) -> str:
    return os.path.splitext(file_name)[1].lower().lstrip(".")


def media_type_for(file_name: str) -> Optional[str]:
    """'image', 'video', or None when the extension is not supported."""
    ext = extension_of(file_name)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def max_upload_bytes() -> int:
    return settings.FORGEGUARD_MAX_UPLOAD_MB * 1024 * 1024


def image_model_path() -> str:
    """IMDModel (ELA + CNN) weights."""
    return os.path.abspath(os.path.join(settings.FORGEGUARD_WEIGHTS_DIR, "model_c1.pth"))


def video_model_path() -> str:
    """EfficientNet-B7 frame classifier weights."""
    return os.path.abspath(os.path.join(settings.FORGEGUARD_WEIGHTS_DIR, "deepfake_detector_b7.pth"))


def error_response_body(message: str, code: str = "error", **extra) -> dict:
    """The error shape every API endpoint returns: {"error": ..., "status": ...}."""
    return {"error": message, "status": code, **extra}


def error_response(message: str, status: int, code: str = "error", **extra) -> JsonResponse:
    """JSON error with the legacy "status" string plus the standard "code" (api/errors.py)."""
    from .errors import with_code

    return JsonResponse(with_code(error_response_body(message, code, **extra), status), status=status)


def validate_upload(file_obj, allowed: frozenset) -> Optional[str]:
    """Return an error message, or None when the upload is acceptable."""
    if extension_of(file_obj.name) not in allowed:
        return f"Unsupported file format. Allowed: {', '.join(sorted(allowed))}"
    if file_obj.size == 0:
        return "File is empty."
    if file_obj.size > max_upload_bytes():
        return f"File size exceeds the {settings.FORGEGUARD_MAX_UPLOAD_MB} MB limit."
    return None


def model_unavailable_response(kind: str) -> JsonResponse:
    """503 for a model that exists but cannot be served (hash mismatch, bad checkpoint).

    The reason is logged server-side and visible in /api/health/, never echoed here.
    """
    return error_response(
        f"The {kind} model is unavailable on this server. See /api/health/.", 503, "MODEL_UNAVAILABLE"
    )


def model_info(path: str) -> dict:
    """Version block attached to detection responses (model name, weights hash, pipeline version)."""
    from core import model_registry

    return model_registry.model_info(path)


def busy_response() -> JsonResponse:
    response = error_response(
        "The server is busy analysing other files. Please retry shortly.", 503, "BUSY"
    )
    response["Retry-After"] = "30"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiting
# ─────────────────────────────────────────────────────────────────────────────

def client_ip(request) -> str:
    if settings.BEHIND_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # The right-most entry is the one appended by our own proxy
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def rate_limited(view):
    """Allow FORGEGUARD_RATE_LIMIT_PER_MINUTE requests per client IP per minute."""

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        limit = settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE
        if limit > 0:
            window = int(time.time() // 60)
            key = f"fg:rl:{client_ip(request)}:{window}"
            cache.add(key, 0, timeout=90)
            try:
                count = cache.incr(key)
            except ValueError:  # key evicted between add() and incr()
                cache.set(key, 1, timeout=90)
                count = 1
            if count > limit:
                response = error_response(
                    f"Rate limit exceeded: at most {limit} detection requests per minute.",
                    429,
                    "RATE_LIMITED",
                )
                response["Retry-After"] = str(60 - int(time.time()) % 60)
                return response
        return view(request, *args, **kwargs)

    return wrapper

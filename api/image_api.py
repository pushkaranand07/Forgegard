"""
image_api.py — POST /api/detect-image/
=======================================
Accepts a multipart upload containing one image file and returns a JSON
payload with both Level-1 (EXIF metadata) and Level-2 (ELA + CNN) findings.

Endpoint
--------
  POST /api/detect-image/

Form fields accepted
--------------------
  image              (preferred field name)
  upload_image_file  (fallback alias)

Response (200 OK)
-----------------
{
    "label":             "AUTHENTIC" | "TAMPERED",
    "predicted_class":   1 | 0,
    "authentic_prob":    float,
    "tampered_prob":     float,
    "confidence_pct":    float,
    "device":            "cpu" | "cuda",
    "original_image":    "<saved filename>" | null,   (null unless FORGEGUARD_KEEP_UPLOADS)
    "processing_time_ms": float,
    "level1": {
        "software_found":     bool,
        "software_signature": str,
        "notes":              [str, ...]
    }
}

Errors use {"error": str, "status": str}: 400 for bad uploads
(INVALID_IMAGE for undecodable/oversized images), 429 when rate limited,
503 when the model is missing or the server is busy.
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.model_registry import ModelUnavailableError
from core.pipeline.image_processor import InvalidImageError, UnsupportedMediaError, detect_image_bytes
from .common import (
    IMAGE_EXTENSIONS, ServerBusy, busy_response, error_response, extension_of,
    image_model_path, inference_slot, model_info, model_unavailable_response,
    rate_limited, validate_upload,
)
from .forms import ImageUploadForm

logger = logging.getLogger("forgeguard.image")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS: frozenset = IMAGE_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_upload(file_name: str, raw_bytes: bytes) -> str:
    """Keep a copy of the upload in MEDIA_ROOT and return its saved filename."""
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    saved_name = f"uploaded_image_{int(time.time())}_{uuid.uuid4().hex[:8]}.{extension_of(file_name)}"
    with open(os.path.join(settings.MEDIA_ROOT, saved_name), "wb") as out:
        out.write(raw_bytes)
    return saved_name


# ─────────────────────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
@rate_limited
def api_detect_image(request):
    """
    POST /api/detect-image/

    Accepts a multipart/form-data POST with an image file.
    Returns a JSON object with combined Level-1 (metadata) and
    Level-2 (ELA + CNN) analysis results.
    """
    start_time = time.time()

    image_file = (
        request.FILES.get("image")
        or request.FILES.get("upload_image_file")
    )
    if image_file is None:
        return error_response("No image file provided. Use field name 'image'.", 400)

    invalid = validate_upload(image_file, ALLOWED_IMAGE_EXTENSIONS)
    if invalid:
        return error_response(invalid, 400)

    model_path = image_model_path()
    if not os.path.isfile(model_path):
        logger.error("Image model weights missing at %s", model_path)
        return error_response(
            "Image manipulation model is not installed on this server.", 503, "model_not_found"
        )

    raw_bytes = image_file.read()

    try:
        with inference_slot():
            result = detect_image_bytes(
                raw_bytes=raw_bytes, model_path=model_path, extension=extension_of(image_file.name)
            )
    except ServerBusy:
        return busy_response()
    except UnsupportedMediaError as exc:
        return error_response(str(exc), 415, "UNSUPPORTED_MEDIA")
    except InvalidImageError as exc:
        return error_response(str(exc), 400, "INVALID_IMAGE")
    except ModelUnavailableError:
        logger.exception("Image model unavailable")
        return model_unavailable_response("image")
    except Exception:
        logger.exception("Image analysis failed for %s", image_file.name)
        return error_response("Image analysis failed due to a server error.", 500)

    payload = result.as_dict()
    payload["model"] = model_info(model_path)
    payload["original_image"] = (
        _save_upload(image_file.name, raw_bytes) if settings.FORGEGUARD_KEEP_UPLOADS else None
    )
    payload["processing_time_ms"] = (time.time() - start_time) * 1000
    return JsonResponse(payload)


def predict_image(request):
    """
    GET /predict-image/ (Render UI with form)
    POST /predict-image/ (Process form upload)
    """
    from django.shortcuts import render

    context = {"form": ImageUploadForm()}

    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        context["form"] = form

        image_file = request.FILES.get("upload_image_file") or request.FILES.get("image")
        if not image_file:
            context["error"] = "No image file provided."
            return render(request, "image_predict.html", context)

        invalid = validate_upload(image_file, ALLOWED_IMAGE_EXTENSIONS)
        if invalid:
            context["error"] = invalid
            return render(request, "image_predict.html", context)

        start_time = time.time()
        raw_bytes = image_file.read()

        try:
            with inference_slot():
                result = detect_image_bytes(raw_bytes=raw_bytes, model_path=image_model_path())
            context.update({
                "output": result.label,
                "confidence": round(max(result.tampered_prob, result.authentic_prob) * 100, 2),
                # The legacy result page displays the uploaded image, so it is always kept
                "original_image": _save_upload(image_file.name, raw_bytes),
                "face_found": False,
                "model_used": f"IMDModel Level-2 ({result.device})",
                "elapsed": round(time.time() - start_time, 2),
                "default_sequence_length": 100,
            })
            if result.software_found:
                context["level1_warning"] = f"Metadata analysis detected editing software: {result.software_signature}"
        except ServerBusy:
            context["error"] = "The server is busy. Please try again shortly."
        except InvalidImageError as exc:
            context["error"] = str(exc)
        except Exception:
            logger.exception("Legacy image analysis failed for %s", image_file.name)
            context["error"] = "Image analysis failed due to a server error."

    return render(request, "image_predict.html", context)

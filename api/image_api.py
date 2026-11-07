"""
image_api.py — POST /api/detect-image/
=======================================
Accepts a multipart upload containing one image file and returns a JSON
payload with both Level-1 (EXIF metadata) and Level-2 (ELA + CNN) findings.

The analysis runs as a background job (api/jobs.py). This endpoint waits up to
FORGEGUARD_SYNC_WAIT_SECONDS for it, which covers images, and otherwise returns
202 with a job id to poll at /api/jobs/<id>/.

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
    "level1": {"software_found": bool, "software_signature": str, "notes": [str, ...]},
    "model": {"model_name": str, "weights_sha256": str, "pipeline_version": str}
}

Errors use {"error": str, "status": str}: 400 for bad uploads (INVALID_IMAGE
for undecodable/oversized images), 415 UNSUPPORTED_MEDIA, 429 when rate
limited, 503 when the model is missing or the queue is full (BUSY).
"""

from __future__ import annotations

import logging
import os

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .common import IMAGE_EXTENSIONS, error_response, image_model_path, rate_limited, validate_upload
from .jobs_api import submit_and_respond

logger = logging.getLogger("forgeguard.image")

ALLOWED_IMAGE_EXTENSIONS: frozenset = IMAGE_EXTENSIONS


@csrf_exempt
@require_POST
@rate_limited
def api_detect_image(request):
    image_file = request.FILES.get("image") or request.FILES.get("upload_image_file")
    if image_file is None:
        return error_response("No image file provided. Use field name 'image'.", 400)

    invalid = validate_upload(image_file, ALLOWED_IMAGE_EXTENSIONS)
    if invalid:
        return error_response(invalid, 400)

    if not os.path.isfile(image_model_path()):
        logger.error("Image model weights missing at %s", image_model_path())
        return error_response("Image manipulation model is not installed on this server.", 503, "model_not_found")

    return submit_and_respond("image", image_file)

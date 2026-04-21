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
    "original_image":    "<saved filename>",
    "level1": {
        "software_found":     bool,
        "software_signature": str,
        "notes":              [str, ...]
    }
}
"""

from __future__ import annotations

import os
import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.pipeline.image_processor import detect_image_bytes
from .forms import ImageUploadForm


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS: frozenset = frozenset(
    {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}
)

# 100 MB — consistent with the video upload limit
_MAX_IMAGE_BYTES: int = 100 * 1024 * 1024  # 104 857 600

# Path to the trained IMDModel weights (inside the cloned external repo)
_IMAGE_MODEL_PATH: str = os.path.abspath(
    os.path.join(
        settings.BASE_DIR,
        "weights",
        "model_c1.pth",
    )
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _upload_dir() -> str:
    """Return (and create if needed) the uploaded_images directory."""
    path = os.path.join(settings.PROJECT_DIR, "uploaded_images")
    os.makedirs(path, exist_ok=True)
    return path


def _allowed_extension(filename: str) -> bool:
    """Return True when the file extension is a supported image format."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_detect_image(request):
    """
    POST /api/detect-image/

    Accepts a multipart/form-data POST with an image file.
    Returns a JSON object with combined Level-1 (metadata) and
    Level-2 (ELA + CNN) analysis results.
    """
    # ── 1. Resolve uploaded file ─────────────────────────────────────────────
    image_file = (
        request.FILES.get("image")
        or request.FILES.get("upload_image_file")
    )
    if image_file is None:
        return JsonResponse(
            {"error": "No image file provided. Use field name 'image'."},
            status=400,
        )

    # ── 2. Validate extension ────────────────────────────────────────────────
    if not _allowed_extension(image_file.name):
        return JsonResponse(
            {
                "error": (
                    f"Unsupported file type: '{image_file.name}'. "
                    f"Allowed: {sorted(ALLOWED_IMAGE_EXTENSIONS)}"
                )
            },
            status=400,
        )

    # ── 3. Validate file size ────────────────────────────────────────────────
    if image_file.size > _MAX_IMAGE_BYTES:
        return JsonResponse(
            {"error": "File too large. Maximum allowed size is 100 MB."},
            status=400,
        )

    # ── 4. Verify model weights exist ────────────────────────────────────────
    if not os.path.isfile(_IMAGE_MODEL_PATH):
        return JsonResponse(
            {
                "error": "Image model weights not found. Ensure model_c1.pth is present.",
                "expected_path": _IMAGE_MODEL_PATH,
            },
            status=500,
        )

    # ── 5. Save upload to disk (for audit / later retrieval) ─────────────────
    ext = image_file.name.rsplit(".", 1)[-1].lower()
    saved_name = f"uploaded_image_{int(time.time())}.{ext}"
    saved_path = os.path.join(_upload_dir(), saved_name)

    raw_bytes = image_file.read()
    with open(saved_path, "wb") as out:
        out.write(raw_bytes)

    # ── 6. Run inference (bytes path — no extra disk I/O) ────────────────────
    try:
        result = detect_image_bytes(
            raw_bytes=raw_bytes,
            model_path=_IMAGE_MODEL_PATH,
        )
        payload = result.as_dict()
        payload["original_image"] = saved_name
        return JsonResponse(payload)

    except Exception as exc:
        return JsonResponse(
            {"error": f"Image analysis failed: {exc}"},
            status=500,
        )


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
            
        if not _allowed_extension(image_file.name):
            context["error"] = f"Unsupported file type. Allowed: {sorted(ALLOWED_IMAGE_EXTENSIONS)}"
            return render(request, "image_predict.html", context)
            
        if image_file.size > _MAX_IMAGE_BYTES:
            context["error"] = "File too large. Maximum allowed size is 100 MB."
            return render(request, "image_predict.html", context)
            
        start_time = time.time()
        ext = image_file.name.rsplit(".", 1)[-1].lower()
        saved_name = f"uploaded_image_{int(time.time())}.{ext}"
        saved_path = os.path.join(_upload_dir(), saved_name)

        raw_bytes = image_file.read()
        with open(saved_path, "wb") as out:
            out.write(raw_bytes)
            
        try:
            result = detect_image_bytes(
                raw_bytes=raw_bytes,
                model_path=_IMAGE_MODEL_PATH,
            )
            context.update({
                "output": result.label,
                "confidence": round(max(result.tampered_prob, result.authentic_prob) * 100, 2),
                "original_image": saved_name,
                "face_found": False,
                "model_used": f"IMDModel Level-2 ({result.device})",
                "elapsed": round(time.time() - start_time, 2),
                "default_sequence_length": 100,
            })
            if result.software_found:
                context["level1_warning"] = f"Metadata analysis detected editing software: {result.software_signature}"
        except Exception as exc:
            context["error"] = f"Image analysis failed: {str(exc)}"
            
    return render(request, "image_predict.html", context)


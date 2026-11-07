"""
health_api.py — GET /api/health/ and GET /api/health/live
=========================================================
Reports whether the service can actually run inference: model weight
availability, compute device, and the upload limits enforced by the
detection endpoints. The frontend uses this to show system status and to
validate files before uploading them.

/api/health/live is a liveness probe: 200 whenever the process can serve
requests. /api/health/ is the readiness probe described below.

Response (200 OK when both models are servable, 503 otherwise)
---------------------------------------------------------------
A model is servable when its file is present, its SHA-256 matches
core/model_manifest.json (or verification is off / it is not listed), and
its last load attempt did not fail.

{
    "status":  "ok" | "degraded",
    "pipeline_version": str,
    "device":  "cpu" | "cuda",
    "gpu_name": str | null,
    "models": {
        "image": {"name": str, "file": str, "present": bool, "loaded": bool, "size_mb": float,
                  "weights_sha256": str | null, "verified": bool | null,
                  "load_state": "loaded" | "failed" | "not_loaded", "load_error": str | null,
                  "healthy": bool},
        "video": {... same ...}
    },
    "limits": {
        "max_upload_mb": int,
        "max_batch_files": int,
        "image_extensions": [str, ...],
        "video_extensions": [str, ...],
        "video_frames_sampled": int
    }
}
"""

from __future__ import annotations

import os

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core import model_registry
from core.pipeline import image_processor, video_processor
from .common import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, image_model_path, video_model_path
from .video_api import NUM_FRAMES


def _model_info(name: str, path: str, loaded: bool) -> dict:
    present = os.path.isfile(path)
    digest, verified = None, None
    if present:
        digest = model_registry.sha256_of(path)
        entry = model_registry.manifest_entry(path)
        if entry is not None and model_registry.verification_enabled():
            verified = digest == entry["sha256"]
    state = model_registry.load_state(path)
    return {
        "name": name,
        "file": os.path.basename(path),
        "present": present,
        "loaded": loaded,
        "size_mb": round(os.path.getsize(path) / (1024 * 1024), 1) if present else 0.0,
        "weights_sha256": digest[:12] if digest else None,
        "verified": verified,
        "load_state": state["state"],
        "load_error": state["error"],
        "healthy": present and verified is not False and state["state"] != "failed",
    }


def _name(path: str, default: str) -> str:
    entry = model_registry.manifest_entry(path)
    return entry["name"] if entry else default


@require_GET
def api_health_live(request) -> JsonResponse:
    """Liveness probe: the process is up and serving requests."""
    return JsonResponse({"status": "ok"})


@require_GET
def api_health(request) -> JsonResponse:
    """Report model availability, compute device, and upload limits."""
    import torch

    cuda = torch.cuda.is_available()
    image_path, video_path = image_model_path(), video_model_path()
    models = {
        "image": _model_info(_name(image_path, "IMDModel (ELA + CNN)"), image_path,
                             image_processor.is_model_loaded(image_path)),
        "video": _model_info(_name(video_path, "EfficientNet-B7 + MTCNN"), video_path,
                             video_processor.is_model_loaded(video_path)),
    }
    healthy = all(m["healthy"] for m in models.values())

    return JsonResponse(
        {
            "status": "ok" if healthy else "degraded",
            "pipeline_version": model_registry.pipeline_version(),
            "device": "cuda" if cuda else "cpu",
            "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
            "models": models,
            "limits": {
                "max_upload_mb": settings.FORGEGUARD_MAX_UPLOAD_MB,
                "max_batch_files": settings.FORGEGUARD_MAX_BATCH_FILES,
                "image_extensions": sorted(IMAGE_EXTENSIONS),
                "video_extensions": sorted(VIDEO_EXTENSIONS),
                "video_frames_sampled": NUM_FRAMES,
            },
        },
        status=200 if healthy else 503,
    )

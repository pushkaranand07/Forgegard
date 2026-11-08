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
import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core import model_registry

from . import jobs
from .analysis import NUM_FRAMES
from .common import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, image_model_path, video_model_path

# A worker that has not reported for this long is considered gone
WORKER_STALE_SECONDS = 30


def _worker_status() -> dict:
    """Is a worker alive, and what has it loaded? In immediate mode (tests) jobs run in-process."""
    try:
        depth = jobs.queue_depth()
        beat = jobs.read_heartbeat()
        reachable = True
    except Exception:  # noqa: BLE001 — Redis and SQLite raise unrelated error types; any failure = unreachable
        depth, beat, reachable = None, None, False

    if jobs.huey.immediate:
        from core.pipeline import image_processor, video_processor

        return {
            "alive": True, "mode": "in-process", "queue_reachable": True, "queue_depth": depth,
            "device": None, "gpu_name": None,
            "loaded": {"image": image_processor.is_model_loaded(image_model_path()),
                       "video": video_processor.is_model_loaded(video_model_path())},
            "load_state": {"image": model_registry.load_state(image_model_path()),
                           "video": model_registry.load_state(video_model_path())},
        }

    age = time.time() - beat["ts"] if beat else None
    alive = reachable and age is not None and age < WORKER_STALE_SECONDS
    models = (beat or {}).get("models", {})
    return {
        "alive": alive, "mode": "worker", "queue_reachable": reachable, "queue_depth": depth,
        "last_seen_seconds": round(age, 1) if age is not None else None,
        "device": (beat or {}).get("device"), "gpu_name": (beat or {}).get("gpu_name"),
        "loaded": {k: models.get(k, {}).get("loaded", False) for k in ("image", "video")},
        "load_state": {k: models.get(k, {}).get("load_state", {"state": "not_loaded", "error": None})
                       for k in ("image", "video")},
    }


def _model_info(name: str, path: str, loaded: bool, state: dict) -> dict:
    present = os.path.isfile(path)
    digest, verified = None, None
    if present:
        digest = model_registry.sha256_of(path)
        entry = model_registry.manifest_entry(path)
        if entry is not None and model_registry.verification_enabled():
            verified = digest == entry["sha256"]
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
    """Liveness probe: the web process is up. No I/O, so it answers under any load."""
    return JsonResponse({"status": "ok"})


@require_GET
def api_health(request) -> JsonResponse:
    """Readiness: weights present and verified, queue reachable, a live worker with models loaded."""
    worker = _worker_status()
    image_path, video_path = image_model_path(), video_model_path()
    models = {
        "image": _model_info(_name(image_path, "IMDModel (ELA + CNN)"), image_path,
                             worker["loaded"]["image"], worker["load_state"]["image"]),
        "video": _model_info(_name(video_path, "EfficientNet-B7 + MTCNN"), video_path,
                             worker["loaded"]["video"], worker["load_state"]["video"]),
    }
    healthy = worker["alive"] and all(m["healthy"] for m in models.values())

    return JsonResponse(
        {
            "status": "ok" if healthy else "degraded",
            "pipeline_version": model_registry.pipeline_version(),
            "device": worker["device"] or "cpu",
            "gpu_name": worker["gpu_name"],
            "models": models,
            "worker": {k: worker[k] for k in ("alive", "mode", "queue_reachable", "queue_depth")}
            | ({"last_seen_seconds": worker["last_seen_seconds"]} if "last_seen_seconds" in worker else {}),
            "limits": {
                "max_upload_mb": settings.FORGEGUARD_MAX_UPLOAD_MB,
                "max_batch_files": settings.FORGEGUARD_MAX_BATCH_FILES,
                "max_queue": settings.FORGEGUARD_MAX_QUEUE,
                "image_extensions": sorted(IMAGE_EXTENSIONS),
                "video_extensions": sorted(VIDEO_EXTENSIONS),
                "video_frames_sampled": NUM_FRAMES,
            },
        },
        status=200 if healthy else 503,
    )

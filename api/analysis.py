"""
api/analysis.py — run one analysis and build its HTTP response body
==================================================================
Executed by the job worker (api/jobs.py), never by a web request thread. Each
``run_*`` function takes the path of a spooled upload plus the client's
original file name and returns ``(http_status, body)``: exactly what the
synchronous endpoints used to return, so the compatibility wrappers can replay
it unchanged.

Model and pipeline modules are imported inside the functions so the web
process, which imports this module only for its constants, never loads torch.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from .common import error_response_body, extension_of, image_model_path, video_model_path

logger = logging.getLogger("forgeguard.analysis")

Result = tuple[int, dict[str, Any]]

# Video pipeline configuration (shared with /api/health/)
DEFAULT_ENCODER = "tf_efficientnet_b7_ns"
NUM_FRAMES = 32
TARGET_FRAME_SIZE = 380

MODEL_UNAVAILABLE_MESSAGE = "The {kind} model is unavailable on this server. See /api/health/."


def _num(value) -> float | None:
    return None if value is None else float(value)


def _model_info(path: str) -> dict[str, Any]:
    from core import model_registry

    return model_registry.model_info(path)


# ─────────────────────────────────────────────────────────────────────────────
# Image  (/api/detect-image/)
# ─────────────────────────────────────────────────────────────────────────────

def run_image(path: str, file_name: str, saved_name: str | None = None) -> Result:
    from core.model_registry import ModelUnavailableError
    from core.pipeline import image_processor

    start = time.time()
    model_path = image_model_path()
    if not os.path.isfile(model_path):
        logger.error("Image model weights missing at %s", model_path)
        return 503, error_response_body("Image manipulation model is not installed on this server.", "model_not_found")

    try:
        with open(path, "rb") as f:
            raw_bytes = f.read()
        result = image_processor.detect_image_bytes(
            raw_bytes=raw_bytes, model_path=model_path, extension=extension_of(file_name)
        )
    except image_processor.UnsupportedMediaError as exc:
        return 415, error_response_body(str(exc), "UNSUPPORTED_MEDIA")
    except image_processor.InvalidImageError as exc:
        return 400, error_response_body(str(exc), "INVALID_IMAGE")
    except ModelUnavailableError:
        logger.exception("Image model unavailable")
        return 503, error_response_body(MODEL_UNAVAILABLE_MESSAGE.format(kind="image"), "MODEL_UNAVAILABLE")
    except Exception:
        logger.exception("Image analysis failed for %s", file_name)
        return 500, error_response_body("Image analysis failed due to a server error.")

    payload = result.as_dict()
    payload["model"] = _model_info(model_path)
    payload["original_image"] = saved_name
    payload["processing_time_ms"] = (time.time() - start) * 1000
    return 200, payload


# ─────────────────────────────────────────────────────────────────────────────
# Video  (/api/detect-video/)
# ─────────────────────────────────────────────────────────────────────────────

def run_video(path: str, file_name: str) -> Result:
    from core.model_registry import ModelUnavailableError
    from core.pipeline import video_processor

    start = time.time()
    model_path = video_model_path()
    if not os.path.isfile(model_path):
        logger.error("Video model weights missing at %s", model_path)
        return 503, error_response_body(
            "Video deepfake detection model is not installed on this server.", "model_not_found"
        )

    try:
        result = video_processor.detect_video_file(
            video_path=path,
            model_path=model_path,
            encoder=DEFAULT_ENCODER,
            device=None,
            num_frames=NUM_FRAMES,
            extract_faces=True,
            target_size=TARGET_FRAME_SIZE,
        )
    except video_processor.InvalidFileException as exc:
        return 400, error_response_body(str(exc), "INVALID_FILE")
    except video_processor.EmptyVideoException as exc:
        return 400, error_response_body(str(exc), "EMPTY_VIDEO")
    except video_processor.NoVisualFramesException as exc:
        return 400, error_response_body(str(exc), "NO_VISUAL_FRAMES")
    except ModelUnavailableError:
        logger.exception("Video model unavailable")
        return 503, error_response_body(MODEL_UNAVAILABLE_MESSAGE.format(kind="video"), "MODEL_UNAVAILABLE")
    except Exception:
        logger.exception("Video analysis failed for %s", file_name)
        return 500, error_response_body("Video analysis failed due to a server error.")

    status_val = "NO_FACE_DETECTED" if result.notes and "NO_FACE_DETECTED" in result.notes else "success"
    return 200, {
        "label": result.label,
        "predicted_class": result.predicted_class,
        "fake_prob": _num(result.fake_prob),
        "real_prob": _num(result.real_prob),
        "confidence_pct": _num(result.confidence_pct),
        "device": result.device,
        "num_frames_processed": result.num_frames_processed,  # deprecated, see below
        "num_frames_sampled": result.num_frames_sampled,
        "num_faces_analyzed": result.num_faces_analyzed,
        "frame_predictions": [float(p) for p in result.frame_predictions],
        "processing_time_ms": (time.time() - start) * 1000,
        "notes": list(result.notes),
        "status": status_val,
        "model": _model_info(model_path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unified  (/api/detect/, and each file of a batch)
# ─────────────────────────────────────────────────────────────────────────────

def run_unified(path: str, file_name: str) -> Result:
    from .unified_detection import detect_file

    start = time.time()
    result = detect_file(path)
    body = result.to_dict()
    body["status"] = "success" if result.label != "ERROR" else "error"
    body["processing_time_ms"] = (time.time() - start) * 1000

    if result.label != "ERROR":
        status = 200
    elif result.model_unavailable:
        status = 503
    elif result.unsupported_media:
        status = 415
    elif result.internal_error:
        status = 500
    else:
        status = 422  # the media itself could not be analysed (corrupt, unreadable, ...)
    return status, body


# Image runners take the kept-upload name as a third argument
RUNNERS: dict[str, Callable[..., Result]] = {"image": run_image, "video": run_video, "unified": run_unified}

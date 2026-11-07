"""
video_api.py — Video Deepfake Detection API
=============================================
POST /api/detect-video/

Accepts a multipart upload containing one video file and returns a JSON
payload with deepfake detection results.

Endpoint
--------
  POST /api/detect-video/

Form fields accepted
--------------------
  video              (preferred field name)
  upload_video_file  (fallback alias)

Response (200 OK)
-----------------
{
    "label":              "REAL" | "FAKE" | "UNSURE",
    "predicted_class":    1 | 0 | -1,
    "fake_prob":          float | null,   (null when no score, e.g. no face)
    "real_prob":          float | null,
    "confidence_pct":     float | null,
    "device":             "cpu" | "cuda",
    "num_frames_processed": int,
    "frame_predictions":  [float, ...],
    "processing_time_ms": float,
    "notes":              [str, ...],
    "status":             "success" | "NO_FACE_DETECTED"
}

Errors use {"error": str, "status": str}: 400 for bad uploads
(INVALID_FILE, EMPTY_VIDEO, NO_VISUAL_FRAMES), 429 when rate limited,
503 when the model is missing or the server is busy.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.pipeline.video_processor import (
    detect_video_file,
    InvalidFileException, EmptyVideoException, NoVisualFramesException
)
from core.model_registry import ModelUnavailableError

from .common import (
    VIDEO_EXTENSIONS, ServerBusy, busy_response, error_response, inference_slot,
    model_info, model_unavailable_response, rate_limited, upload_to_temp_file,
    validate_upload, video_model_path,
)

logger = logging.getLogger("forgeguard.video")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Supported video formats
ALLOWED_VIDEO_EXTENSIONS = VIDEO_EXTENSIONS

# Model configuration
DEFAULT_ENCODER = "tf_efficientnet_b7_ns"
NUM_FRAMES = 32
TARGET_FRAME_SIZE = 380


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_video_file(file_obj: Any) -> tuple[bool, str]:
    """
    Validate uploaded video file.

    Returns:
        (is_valid, error_message)
    """
    error = validate_upload(file_obj, ALLOWED_VIDEO_EXTENSIONS)
    return error is None, error or ""


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

def _num(value):
    return None if value is None else float(value)


@csrf_exempt
@require_POST
@rate_limited
def api_detect_video(request) -> JsonResponse:
    """
    Video deepfake detection API endpoint.

    Accepts a video file upload and returns deepfake detection results.
    """
    start_time = time.time()

    # Get video file from request
    video_file = None
    for field_name in ['video', 'upload_video_file']:
        if field_name in request.FILES:
            video_file = request.FILES[field_name]
            break

    if video_file is None:
        return error_response('No video file provided', 400)

    is_valid, error_msg = validate_video_file(video_file)
    if not is_valid:
        return error_response(error_msg, 400)

    model_path = video_model_path()
    if not os.path.isfile(model_path):
        logger.error("Video model weights missing at %s", model_path)
        return error_response(
            'Video deepfake detection model is not installed on this server.',
            503,
            'model_not_found',
        )

    try:
        with upload_to_temp_file(video_file) as temp_path, inference_slot():
            result = detect_video_file(
                video_path=temp_path,
                model_path=model_path,
                encoder=DEFAULT_ENCODER,
                device=None,  # Auto-select
                num_frames=NUM_FRAMES,
                extract_faces=True,
                target_size=TARGET_FRAME_SIZE
            )
    except ServerBusy:
        return busy_response()
    except InvalidFileException as e:
        return error_response(str(e), 400, 'INVALID_FILE')
    except EmptyVideoException as e:
        return error_response(str(e), 400, 'EMPTY_VIDEO')
    except NoVisualFramesException as e:
        return error_response(str(e), 400, 'NO_VISUAL_FRAMES')
    except ModelUnavailableError:
        logger.exception("Video model unavailable")
        return model_unavailable_response("video")
    except Exception:
        logger.exception("Video analysis failed for %s", video_file.name)
        return error_response('Video analysis failed due to a server error.', 500)

    status_val = 'success'
    if result.notes and "NO_FACE_DETECTED" in result.notes:
        status_val = 'NO_FACE_DETECTED'

    return JsonResponse({
        'label': result.label,
        'predicted_class': result.predicted_class,
        'fake_prob': _num(result.fake_prob),
        'real_prob': _num(result.real_prob),
        'confidence_pct': _num(result.confidence_pct),
        'device': result.device,
        'num_frames_processed': result.num_frames_processed,
        'frame_predictions': [float(p) for p in result.frame_predictions],
        'processing_time_ms': (time.time() - start_time) * 1000,
        'notes': list(result.notes),
        'status': status_val,
        'model': model_info(model_path),
    }, status=200)

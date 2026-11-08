"""
video_api.py — POST /api/detect-video/
======================================
Accepts a multipart upload containing one video file and returns deepfake
detection results.

The analysis runs as a background job (api/jobs.py). This endpoint waits up to
FORGEGUARD_SYNC_WAIT_SECONDS for it; a video usually takes longer on CPU, so
expect 202 with a job id to poll at /api/jobs/<id>/.

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
    "num_frames_sampled":  int,            frames read from the video
    "num_faces_analyzed":  int,            faces classified (= len(frame_predictions))
    "num_frames_processed": int,           deprecated: faces if decided, else frames
    "frame_predictions":  [float, ...],
    "processing_time_ms": float,
    "notes":              [str, ...],
    "status":             "success" | "NO_FACE_DETECTED",
    "model":              {...}
}

Errors use {"error": str, "status": str}: 400 for bad uploads (INVALID_FILE,
EMPTY_VIDEO, NO_VISUAL_FRAMES), 429 when rate limited, 503 when the model is
missing or the queue is full (BUSY).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .analysis import DEFAULT_ENCODER, NUM_FRAMES, TARGET_FRAME_SIZE  # noqa: F401  (re-exported)
from .common import VIDEO_EXTENSIONS, error_response, rate_limited, validate_upload, video_model_path
from .jobs_api import submit_and_respond

logger = logging.getLogger("forgeguard.video")

ALLOWED_VIDEO_EXTENSIONS = VIDEO_EXTENSIONS


def validate_video_file(file_obj: Any) -> tuple[bool, str]:
    """(is_valid, error_message) for an uploaded video."""
    error = validate_upload(file_obj, ALLOWED_VIDEO_EXTENSIONS)
    return error is None, error or ""


@csrf_exempt
@require_POST
@rate_limited
def api_detect_video(request):
    video_file = request.FILES.get("video") or request.FILES.get("upload_video_file")
    if video_file is None:
        return error_response("No video file provided", 400)

    is_valid, error_msg = validate_video_file(video_file)
    if not is_valid:
        return error_response(error_msg, 400)

    if not os.path.isfile(video_model_path()):
        logger.error("Video model weights missing at %s", video_model_path())
        return error_response("Video deepfake detection model is not installed on this server.", 503, "model_not_found")

    return submit_and_respond("video", video_file)

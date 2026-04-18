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
    "label":              "REAL" | "FAKE",
    "predicted_class":    1 | 0,
    "fake_prob":          float,
    "real_prob":          float,
    "confidence_pct":     float,
    "device":             "cpu" | "cuda",
    "num_frames_processed": int,
    "frame_predictions":  [float, ...],
    "processing_time_ms": float
}
"""

from __future__ import annotations

import os
import time
import tempfile
import logging
from typing import Dict, Any

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from core.pipeline.video_processor import (
    detect_video_file, 
    InvalidFileException, EmptyVideoException, NoVisualFramesException
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# 100 MB video limit
MAX_VIDEO_SIZE = 100 * 1024 * 1024

# Supported video formats
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'webm', 'mov', 'mkv', 'flv', '3gp', 'wmv', 'gif'}

# Model configuration
DEFAULT_ENCODER = "tf_efficientnet_b7_ns"
NUM_FRAMES = 32
TARGET_FRAME_SIZE = 380

# Path to model weights
MODEL_WEIGHTS_DIR = os.path.join(settings.BASE_DIR, 'weights')
DEFAULT_MODEL_PATH = os.path.join(MODEL_WEIGHTS_DIR, 'deepfake_detector_b7.pth')


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_video_file(file_obj: Any) -> tuple[bool, str]:
    """
    Validate uploaded video file.
    
    Args:
        file_obj: Django uploaded file object
    
    Returns:
        (is_valid, error_message)
    """
    # Check file size
    if file_obj.size > MAX_VIDEO_SIZE:
        return False, f"File size exceeds {MAX_VIDEO_SIZE / (1024*1024):.0f}MB limit"
    
    # Check file extension
    file_name = file_obj.name.lower()
    if not any(file_name.endswith(f".{ext}") for ext in ALLOWED_VIDEO_EXTENSIONS):
        return False, f"Unsupported video format. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"
    
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
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
        return JsonResponse({
            'error': 'No video file provided',
            'status': 'error'
        }, status=400)
    
    # Validate video file
    is_valid, error_msg = validate_video_file(video_file)
    if not is_valid:
        return JsonResponse({
            'error': error_msg,
            'status': 'error'
        }, status=400)
    
    # Save uploaded file temporarily
    temp_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos')
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_path = os.path.join(temp_dir, video_file.name)
    
    try:
        # Write uploaded file to disk
        with open(temp_path, 'wb+') as dest:
            for chunk in video_file.chunks():
                dest.write(chunk)
        
        # Check if model file exists
        if not os.path.exists(DEFAULT_MODEL_PATH):
            return JsonResponse({
                'error': (
                    'Video deepfake detection model not found. '
                    'Please download the model weights and place them in the models/ directory. '
                    'See SETUP_VIDEO_MODEL.md for instructions.'
                ),
                'status': 'model_not_found',
                'model_path': DEFAULT_MODEL_PATH
            }, status=503)  # Use 503 Service Unavailable for missing resources
        
        # Run inference
        result = detect_video_file(
            video_path=temp_path,
            model_path=DEFAULT_MODEL_PATH,
            encoder=DEFAULT_ENCODER,
            device=None,  # Auto-select
            num_frames=NUM_FRAMES,
            extract_faces=True,
            target_size=TARGET_FRAME_SIZE
        )
        
        # Format response
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        status_val = 'success'
        if result.notes and "NO_FACE_DETECTED" in result.notes:
            status_val = 'NO_FACE_DETECTED'
            
        response_data = {
            'label': result.label,
            'predicted_class': result.predicted_class,
            'fake_prob': float(result.fake_prob),
            'real_prob': float(result.real_prob),
            'confidence_pct': float(result.confidence_pct),
            'device': result.device,
            'num_frames_processed': result.num_frames_processed,
            'frame_predictions': [float(p) for p in result.frame_predictions],
            'processing_time_ms': processing_time,
            'status': status_val
        }
        
        return JsonResponse(response_data, status=200)
    
    
    except InvalidFileException as e:
        return JsonResponse({
            'error': str(e),
            'status': 'INVALID_FILE'
        }, status=400)
        
    except EmptyVideoException as e:
        return JsonResponse({
            'error': str(e),
            'status': 'EMPTY_VIDEO'
        }, status=400)
        
    except NoVisualFramesException as e:
        return JsonResponse({
            'error': str(e),
            'status': 'NO_VISUAL_FRAMES'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Processing error: {str(e)}',
            'status': 'error'
        }, status=500)
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


@csrf_exempt
@require_POST
def predict_video(request):
    """
    Legacy endpoint for video deepfake detection results page.
    
    Redirects to unified API endpoint and renders results page.
    """
    # Get video file
    video_file = request.FILES.get('upload_video_file') or request.FILES.get('video')
    
    if video_file is None:
        return JsonResponse({'error': 'No video file provided'}, status=400)
    
    # Validate
    is_valid, error_msg = validate_video_file(video_file)
    if not is_valid:
        return JsonResponse({'error': error_msg}, status=400)
    
    # Process using API
    request.FILES['video'] = video_file
    api_response = api_detect_video(request)
    
    return api_response

"""
unified_api.py — Unified Image & Video Forgery Detection API
============================================================
POST /api/detect/

Single endpoint that auto-detects media type and runs appropriate detection.
"""

from __future__ import annotations

import time
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .common import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, ServerBusy,
    busy_response, error_response, inference_slot, rate_limited, validate_upload,
)
from .unified_detection import detect_uploaded_file


ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# Unified API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
@rate_limited
def api_detect(request) -> JsonResponse:
    """
    Unified forgery detection endpoint for images and videos.
    
    Automatically detects media type and applies appropriate detection method:
    - Images: ELA + CNN (image manipulation detection)
    - Videos: EfficientNet frame classifier (deepfake detection)
    
    Request:
        POST /api/detect/
        
        Form fields:
          - file (required): Image or video file
    
    Response (200 OK):
        {
            "media_type": "image" | "video",
            "label": "AUTHENTIC" | "TAMPERED" | "REAL" | "FAKE" | "ERROR",
            "confidence_pct": float,
            "device": "cpu" | "cuda",
            "processing_time_ms": float,
            
            // For images:
            "level1": {
                "software_found": bool,
                "software_signature": str,
                "notes": [str]
            },
            "level2": {
                "authentic_prob": float,
                "tampered_prob": float,
                "method": "ELA + CNN"
            },
            
            // For videos:
            "num_frames_processed": int,
            "frame_predictions": [float, ...]
        }
    """
    start_time = time.time()
    
    # Get file from request
    file_obj = None
    for field_name in ['file', 'media', 'upload_file']:
        if field_name in request.FILES:
            file_obj = request.FILES[field_name]
            break
    
    if file_obj is None:
        return error_response('No file provided. Use field name: "file"', 400)

    invalid = validate_upload(file_obj, ALLOWED_EXTENSIONS)
    if invalid:
        return error_response(invalid, 400)

    try:
        with inference_slot():
            result = detect_uploaded_file(file_obj)
    except ServerBusy:
        return busy_response()

    response_data = result.to_dict()
    response_data['status'] = 'success' if result.label != 'ERROR' else 'error'
    response_data['processing_time_ms'] = (time.time() - start_time) * 1000

    if result.label != 'ERROR':
        status = 200
    else:
        # 422: the media itself could not be analysed (corrupt, unreadable, ...)
        status = 500 if result.internal_error else 422
    return JsonResponse(response_data, status=status)


@csrf_exempt
@require_POST
@rate_limited
def api_detect_multi(request) -> JsonResponse:
    """
    Batch detection endpoint for multiple files.
    
    Request:
        POST /api/detect/batch
        
        Form fields:
          - file[0], file[1], ... : Multiple files
    
    Response:
        {
            "status": "success" | "partial_error" | "error",
            "results": [
                { detection result 1 },
                { detection result 2 },
                ...
            ],
            "errors": [
                { "file_index": 0, "error": "reason" },
                ...
            ],
            "processing_time_ms": float
        }
    """
    start_time = time.time()
    
    # Get all files
    files = request.FILES.getlist('file')

    if not files:
        return error_response('No files provided', 400)

    max_files = settings.FORGEGUARD_MAX_BATCH_FILES
    if len(files) > max_files:
        return error_response(f'Too many files: at most {max_files} per batch.', 400)

    results = []
    errors = []

    for idx, file_obj in enumerate(files):
        invalid = validate_upload(file_obj, ALLOWED_EXTENSIONS)
        if invalid:
            errors.append({'file_index': idx, 'file_name': file_obj.name, 'error': invalid})
            continue

        # One slot per file, so other clients interleave with a long batch
        try:
            with inference_slot():
                result = detect_uploaded_file(file_obj)
        except ServerBusy:
            errors.append({
                'file_index': idx,
                'file_name': file_obj.name,
                'error': 'Server busy; file was not analysed. Retry it later.',
            })
            continue

        if result.label == 'ERROR':
            errors.append({
                'file_index': idx,
                'file_name': file_obj.name,
                'error': result.error or 'Detection failed'
            })
            continue

        result_dict = result.to_dict()
        result_dict['file_index'] = idx
        result_dict['file_name'] = file_obj.name
        results.append(result_dict)

    # Determine overall status
    if not results and errors:
        overall_status = 'error'
    elif errors:
        overall_status = 'partial_error'
    else:
        overall_status = 'success'
    
    response_data = {
        'status': overall_status,
        'results': results,
        'errors': errors,
        'num_success': len(results),
        'num_errors': len(errors),
        'processing_time_ms': (time.time() - start_time) * 1000
    }
    
    return JsonResponse(response_data, status=200 if overall_status != 'error' else 400)

"""
unified_api.py — Unified Image & Video Forgery Detection API
============================================================
POST /api/detect/

Single endpoint that auto-detects media type and runs appropriate detection.
"""

from __future__ import annotations

import time
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .unified_detection import detect_file_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

ALLOWED_EXTENSIONS = {
    # Images
    'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif',
    # Videos
    'mp4', 'avi', 'webm', 'mov', 'mkv', 'flv', '3gp', 'wmv'
}


# ─────────────────────────────────────────────────────────────────────────────
# Unified API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
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
        return JsonResponse({
            'error': 'No file provided. Use field name: "file"',
            'status': 'error'
        }, status=400)
    
    # Validate file
    if file_obj.size > MAX_FILE_SIZE:
        return JsonResponse({
            'error': f'File size exceeds {MAX_FILE_SIZE / (1024*1024):.0f}MB limit',
            'status': 'error'
        }, status=400)
    
    # Check file extension
    file_name = file_obj.name.lower()
    ext = file_name.split('.')[-1] if '.' in file_name else ''
    
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({
            'error': f'Unsupported file format. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
            'status': 'error'
        }, status=400)
    
    try:
        # Read file bytes
        file_bytes = file_obj.read()
        
        if not file_bytes:
            return JsonResponse({
                'error': 'File is empty',
                'status': 'error'
            }, status=400)
        
        # Run unified detection
        result = detect_file_bytes(
            file_bytes=file_bytes,
            file_name=file_name,
            auto_detect_type=True,
            device=None  # Auto-select
        )
        
        # Format response
        response_data = result.to_dict()
        response_data['status'] = 'success' if result.label != 'ERROR' else 'error'
        response_data['processing_time_ms'] = (time.time() - start_time) * 1000
        
        return JsonResponse(response_data, status=200)
    
    except Exception as e:
        return JsonResponse({
            'error': f'Processing error: {str(e)}',
            'status': 'error',
            'processing_time_ms': (time.time() - start_time) * 1000
        }, status=500)


@csrf_exempt
@require_POST
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
        return JsonResponse({
            'error': 'No files provided',
            'status': 'error'
        }, status=400)
    
    results = []
    errors = []
    
    for idx, file_obj in enumerate(files):
        try:
            # Validate
            if file_obj.size > MAX_FILE_SIZE:
                errors.append({
                    'file_index': idx,
                    'file_name': file_obj.name,
                    'error': f'File size exceeds {MAX_FILE_SIZE / (1024*1024):.0f}MB'
                })
                continue
            
            # Check extension
            file_name = file_obj.name.lower()
            ext = file_name.split('.')[-1] if '.' in file_name else ''
            
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({
                    'file_index': idx,
                    'file_name': file_name,
                    'error': 'Unsupported file format'
                })
                continue
            
            # Detect
            file_bytes = file_obj.read()
            result = detect_file_bytes(file_bytes, file_name)
            
            result_dict = result.to_dict()
            result_dict['file_index'] = idx
            result_dict['file_name'] = file_name
            results.append(result_dict)
        
        except Exception as e:
            errors.append({
                'file_index': idx,
                'file_name': file_obj.name,
                'error': str(e)
            })
    
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

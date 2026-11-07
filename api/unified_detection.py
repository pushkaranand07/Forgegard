"""
unified_detection.py — Unified Image & Video Forgery Detection
==============================================================

Combines image manipulation detection (ELA + CNN) and video deepfake 
detection (EfficientNet frame classifier) into a unified API.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

import torch

from core.pipeline.image_processor import InvalidImageError, UnsupportedMediaError, detect_image_bytes
from core.pipeline.video_processor import (
    detect_video_file,
    InvalidFileException, EmptyVideoException, NoVisualFramesException,
)

from core.model_registry import ModelUnavailableError

from . import common

logger = logging.getLogger("forgeguard.unified")


# ─────────────────────────────────────────────────────────────────────────────
# Unified Result Type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UnifiedDetectionResult:
    """Unified result from image or video forgery detection."""
    
    media_type: str  # "image" or "video"
    label: str  # "AUTHENTIC", "TAMPERED", "REAL", "FAKE", "UNSURE", "ERROR"
    confidence_pct: Optional[float]  # None when there is no score
    device: str
    processing_time_ms: float
    
    # Image-specific fields
    image_level1: Optional[Dict[str, Any]] = None
    image_level2: Optional[Dict[str, Any]] = None
    
    # Video-specific fields
    num_frames_processed: Optional[int] = None
    frame_predictions: Optional[list] = None

    # Pipeline notes (e.g. NO_FACE_DETECTED) and failure reason, if any
    notes: Optional[list] = None
    error: Optional[str] = None
    # True when the failure was ours (bug, OOM, ...) rather than a bad upload
    internal_error: bool = False
    # True when the model exists but cannot be served (hash mismatch, bad checkpoint)
    model_unavailable: bool = False
    # True when the file is an image format ForgeGuard does not decode (HTTP 415)
    unsupported_media: bool = False
    # Version block: model name, weights hash, pipeline version
    model: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        result = {
            'media_type': self.media_type,
            'label': self.label,
            'confidence_pct': self.confidence_pct,
            'device': self.device,
            'processing_time_ms': self.processing_time_ms,
        }
        
        if self.image_level1:
            result['level1'] = self.image_level1
        if self.image_level2:
            result['level2'] = self.image_level2
        if self.num_frames_processed is not None:
            result['num_frames_processed'] = self.num_frames_processed
        if self.frame_predictions:
            result['frame_predictions'] = self.frame_predictions
        if self.notes:
            result['notes'] = self.notes
        if self.error:
            result['error'] = self.error
        if self.model:
            result['model'] = self.model
        
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Detection Functions
# ─────────────────────────────────────────────────────────────────────────────

def detect_file(
    file_path: str,
    auto_detect_type: bool = True,
    image_model_path: Optional[str] = None,
    video_model_path: Optional[str] = None,
    device: Optional[str] = None
) -> UnifiedDetectionResult:
    """
    Detect forgery in an image or video file.
    
    Args:
        file_path: Path to media file
        auto_detect_type: Whether to auto-detect media type from file extension
        image_model_path: Path to image model weights
        video_model_path: Path to video model weights
        device: Computation device ("cuda" or "cpu")
    
    Returns:
        UnifiedDetectionResult with detection results
    """
    import time
    start_time = time.time()
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if not os.path.exists(file_path):
        return UnifiedDetectionResult(
            media_type="unknown",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="File not found.",
        )
    
    # Extension decides the model (same rules as the upload validation)
    media_type = common.media_type_for(file_path)

    # Process based on media type
    if media_type == 'image':
        return _detect_image(file_path, image_model_path, device, start_time)
    elif media_type == 'video':
        return _detect_video(file_path, video_model_path, device, start_time)
    else:
        return UnifiedDetectionResult(
            media_type="unknown",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="Could not determine media type from file extension.",
        )


def _detect_image(
    file_path: str,
    model_path: Optional[str] = None,
    device: Optional[str] = None,
    start_time: float = None
) -> UnifiedDetectionResult:
    """Detect forgery in an image file."""
    import time
    
    if start_time is None:
        start_time = time.time()
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if model_path is None:
        model_path = common.image_model_path()
    
    try:
        # Read image bytes
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        # Run image detection
        imd_result = detect_image_bytes(image_bytes, model_path, extension=common.extension_of(file_path))
        
        # Map to unified result
        label = "AUTHENTIC" if imd_result.predicted_class == 1 else "TAMPERED"
        confidence = max(imd_result.authentic_prob, imd_result.tampered_prob) * 100
        
        processing_time = (time.time() - start_time) * 1000
        
        return UnifiedDetectionResult(
            media_type="image",
            label=label,
            confidence_pct=confidence,
            device=device,
            processing_time_ms=processing_time,
            image_level1={
                'software_found': imd_result.software_found,
                'software_signature': imd_result.software_signature,
                'notes': list(imd_result.level1_notes),
            },
            image_level2={
                'authentic_prob': float(imd_result.authentic_prob),
                'tampered_prob': float(imd_result.tampered_prob),
                'method': 'ELA + CNN',
            },
            model=common.model_info(model_path),
        )
    
    except UnsupportedMediaError as e:
        return UnifiedDetectionResult(
            media_type="image",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error=str(e),
            unsupported_media=True,
        )
    except InvalidImageError as e:
        error = str(e)
    except ModelUnavailableError:
        logger.exception("Image model unavailable")
        return UnifiedDetectionResult(
            media_type="image",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="The image model is unavailable on this server.",
            model_unavailable=True,
        )
    except Exception:
        logger.exception("Unified image detection failed")
        return UnifiedDetectionResult(
            media_type="image",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="Image analysis failed due to a server error.",
            internal_error=True,
        )

    return UnifiedDetectionResult(
        media_type="image",
        label="ERROR",
        confidence_pct=None,
        device=device,
        processing_time_ms=(time.time() - start_time) * 1000,
        error=error,
    )


def _detect_video(
    file_path: str,
    model_path: Optional[str] = None,
    device: Optional[str] = None,
    start_time: float = None
) -> UnifiedDetectionResult:
    """Detect deepfakes in a video file."""
    import time
    
    if start_time is None:
        start_time = time.time()
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if model_path is None:
        model_path = common.video_model_path()
    
    try:
        # Run video detection
        vmd_result = detect_video_file(
            file_path,
            model_path,
            device=device,
            num_frames=32,
            extract_faces=True,
            target_size=380
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return UnifiedDetectionResult(
            media_type="video",
            label=vmd_result.label,
            confidence_pct=vmd_result.confidence_pct,
            device=device,
            processing_time_ms=processing_time,
            num_frames_processed=vmd_result.num_frames_processed,
            frame_predictions=vmd_result.frame_predictions,
            notes=list(vmd_result.notes) or None,
            model=common.model_info(model_path),
        )
    
    except (InvalidFileException, EmptyVideoException, NoVisualFramesException) as e:
        error = str(e)
    except ModelUnavailableError:
        logger.exception("Video model unavailable")
        return UnifiedDetectionResult(
            media_type="video",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="The video model is unavailable on this server.",
            model_unavailable=True,
        )
    except Exception:
        logger.exception("Unified video detection failed")
        return UnifiedDetectionResult(
            media_type="video",
            label="ERROR",
            confidence_pct=None,
            device=device,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="Video analysis failed due to a server error.",
            internal_error=True,
        )

    return UnifiedDetectionResult(
        media_type="video",
        label="ERROR",
        confidence_pct=None,
        device=device,
        processing_time_ms=(time.time() - start_time) * 1000,
        error=error,
    )


def detect_file_bytes(
    file_bytes: bytes,
    file_name: str,
    auto_detect_type: bool = True,
    image_model_path: Optional[str] = None,
    video_model_path: Optional[str] = None,
    device: Optional[str] = None
) -> UnifiedDetectionResult:
    """
    Detect forgery in file bytes.
    
    Args:
        file_bytes: Raw file bytes
        file_name: Filename for mime type detection
        auto_detect_type: Whether to auto-detect media type
        image_model_path: Path to image model
        video_model_path: Path to video model
        device: Computation device
    
    Returns:
        UnifiedDetectionResult
    """
    import tempfile
    import time
    
    start_time = time.time()
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(file_name)[1], delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        result = detect_file(
            tmp_path,
            auto_detect_type=auto_detect_type,
            image_model_path=image_model_path,
            video_model_path=video_model_path,
            device=device
        )
        
        # Update processing time to include file I/O
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result
    
    finally:
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def detect_uploaded_file(file_obj, device: Optional[str] = None) -> UnifiedDetectionResult:
    """Detect forgery in a Django upload, streaming it to a scratch file first."""
    import time

    start_time = time.time()
    with common.upload_to_temp_file(file_obj) as tmp_path:
        result = detect_file(tmp_path, device=device)
    # Include the upload's disk I/O in the reported time
    result.processing_time_ms = (time.time() - start_time) * 1000
    return result

"""Image manipulation detection pipeline (inference-only)."""

from .imd import (
    IMDModel,
    ImageDetectionResult,
    detect_image_file,
    detect_image_bytes,
    load_model,
)

__all__ = [
    'IMDModel',
    'ImageDetectionResult',
    'detect_image_file',
    'detect_image_bytes',
    'load_model',
]

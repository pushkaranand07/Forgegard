"""Video deepfake detection pipeline (based on DFDC challenge winning solution)."""

from .vmd import (
    DeepFakeClassifier,
    VideoReader,
    FaceExtractor,
    detect_video_file,
    detect_video_frames,
    load_model,
    confident_strategy,
)

__all__ = [
    'DeepFakeClassifier',
    'VideoReader',
    'FaceExtractor',
    'detect_video_file',
    'detect_video_frames',
    'load_model',
    'confident_strategy',
]

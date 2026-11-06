"""
core/pipeline/video_processor.py
================================
Video deepfake detection: inference path ported from the DFDC 1st-place
solution by Selim Seferbekov (https://github.com/selimsef/dfdc_deepfake_challenge,
MIT). The weights are upstream's pretrained checkpoint; see CREDITS.md.

Differences from upstream kernel_utils.py: only the highest-confidence face per
frame is classified (upstream classifies all faces), and a single checkpoint is
used (upstream averages an ensemble).

Public entry-points
-------------------
  load_model(model_path, device=None)              -> nn.Module
  detect_video_file(video_path, model_path, ...)  -> VideoDetectionResult
  detect_video_frames(frames, model_path, ...)    -> VideoDetectionResult
"""

from __future__ import annotations

import os
import threading
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn.modules.dropout import Dropout
from torch.nn.modules.linear import Linear
from torch.nn.modules.pooling import AdaptiveAvgPool2d
from torchvision.transforms import Normalize

logger = logging.getLogger("forgeguard.video")

try:
    from facenet_pytorch.models.mtcnn import MTCNN
except ImportError:
    MTCNN = None

try:
    import timm as _timm
    _TIMM_AVAILABLE = True
except ImportError:
    _TIMM_AVAILABLE = False


def _make_efficientnet(model_name: str, drop_path_rate: float = 0.2):
    """Factory using timm.create_model() — works across all timm versions."""
    if not _TIMM_AVAILABLE:
        return None
    return lambda: _timm.create_model(
        model_name,
        pretrained=False,
        drop_path_rate=drop_path_rate
    )


# ─────────────────────────────────────────────────────────────────────────────
# Normalization constants
# ─────────────────────────────────────────────────────────────────────────────

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
normalize_transform = Normalize(IMAGENET_MEAN, IMAGENET_STD)


# ─────────────────────────────────────────────────────────────────────────────
# Encoder parameters mapping
# ─────────────────────────────────────────────────────────────────────────────

# timm 1.0+ renamed _ns models to dot notation (e.g. tf_efficientnet_b7_ns → tf_efficientnet_b7.ns_jft_in1k)
# Keep old keys as aliases so existing checkpoints and configs continue to work.
encoder_params = {
    "tf_efficientnet_b7.ns_jft_in1k": {
        "features": 2560,
        "init_op": _make_efficientnet("tf_efficientnet_b7.ns_jft_in1k", drop_path_rate=0.2)
    },
    "tf_efficientnet_b6.ns_jft_in1k": {
        "features": 2304,
        "init_op": _make_efficientnet("tf_efficientnet_b6.ns_jft_in1k", drop_path_rate=0.2)
    },
    "tf_efficientnet_b5.ns_jft_in1k": {
        "features": 2048,
        "init_op": _make_efficientnet("tf_efficientnet_b5.ns_jft_in1k", drop_path_rate=0.2)
    },
    "tf_efficientnet_b4.ns_jft_in1k": {
        "features": 1792,
        "init_op": _make_efficientnet("tf_efficientnet_b4.ns_jft_in1k", drop_path_rate=0.5)
    },
}
# Backward-compatible aliases (deprecated _ns names still accepted)
encoder_params["tf_efficientnet_b7_ns"] = encoder_params["tf_efficientnet_b7.ns_jft_in1k"]
encoder_params["tf_efficientnet_b6_ns"] = encoder_params["tf_efficientnet_b6.ns_jft_in1k"]
encoder_params["tf_efficientnet_b5_ns"] = encoder_params["tf_efficientnet_b5.ns_jft_in1k"]
encoder_params["tf_efficientnet_b4_ns"] = encoder_params["tf_efficientnet_b4.ns_jft_in1k"]


# ─────────────────────────────────────────────────────────────────────────────
# Model Architecture
# ─────────────────────────────────────────────────────────────────────────────

class DeepFakeClassifier(nn.Module):
    """
    EfficientNet-based binary classifier for deepfake detection.
    
    Architecture from the upstream DFDC solution.

    Input: RGB image tensor normalized to ImageNet statistics
    Output: one logit per face; sigmoid(logit) = P(fake)
    """
    
    def __init__(self, encoder: str = "tf_efficientnet_b7_ns", dropout_rate: float = 0.0) -> None:
        super().__init__()
        if encoder not in encoder_params:
            raise ValueError(f"Unknown encoder: {encoder}. Available: {list(encoder_params.keys())}")
        
        params = encoder_params[encoder]
        
        if params["init_op"] is None:
            raise ImportError(
                "EfficientNet encoder not available. "
                "Install timm: pip install timm>=0.9.0"
            )
        
        self.encoder = params["init_op"]()
        self.avg_pool = AdaptiveAvgPool2d((1, 1))
        self.dropout = Dropout(dropout_rate)
        self.fc = Linear(params["features"], 1)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input tensor of shape (B, C, H, W)
        Returns:
            Logits of shape (B, 1)
        """
        x = self.encoder.forward_features(x)
        x = self.avg_pool(x).flatten(1)
        x = self.dropout(x)
        x = self.fc(x)
        return x


# ─────────────────────────────────────────────────────────────────────────────
# Video Reading Utilities
# ─────────────────────────────────────────────────────────────────────────────

class InvalidFileException(Exception): pass
class EmptyVideoException(Exception): pass
class NoVisualFramesException(Exception): pass

class VideoReader:
    """Helper class for reading frames from a video file."""
    
    def __init__(self, verbose: bool = True, insets: Tuple[int, int] = (0, 0)):
        """
        Args:
            verbose: Whether to print warnings and error messages
            insets: Amount to inset the image by as (width_pct, height_pct)
        """
        self.verbose = verbose
        self.insets = insets
    
    def read_frames(
        self,
        path: str,
        num_frames: int,
        jitter: int = 0,
        seed: Optional[int] = None
    ) -> Optional[np.ndarray]:
        """
        Reads evenly spaced frames from a video file.
        
        Args:
            path: Video file path
            num_frames: Number of frames to extract
            jitter: Random offset range for frame indices
            seed: Random seed for jitter reproducibility
        
        Returns:
            Array of shape (num_frames, H, W, 3) or None if error
        """
        assert num_frames > 0
        
        if not os.path.getsize(path) > 0:
            raise EmptyVideoException("Video file is 0 bytes")
            
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            raise InvalidFileException("Cannot open video file")
            
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if frame_count <= 0:
            raise NoVisualFramesException("Video has no frames (audio only or corrupt)")
            
        # Calculate evenly spaced frame indices
        frame_idxs = np.linspace(0, frame_count - 1, num_frames, endpoint=True, dtype=int)
        
        if jitter > 0:
            np.random.seed(seed)
            jitter_offsets = np.random.randint(-jitter, jitter, len(frame_idxs))
            frame_idxs = np.clip(frame_idxs + jitter_offsets, 0, frame_count - 1)
        
        frames = []
        for idx in frame_idxs:
            capture.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = capture.read()
            if ret:
                frames.append(frame)
        
        capture.release()
        
        if len(frames) == 0:
            raise NoVisualFramesException("Could not extract any visual frames")
        
        return np.array(frames)


class FaceDetectionEngine:
    """
    Detects and extracts faces from video frames using MTCNN.

    Crop settings match upstream kernel_utils.py (FaceExtractor); deviating
    from them causes a train/inference mismatch that pushes real videos
    towards FAKE. Unlike upstream, extract_face keeps only one face per frame.

    Upstream settings:
        detector = MTCNN(margin=0, thresholds=[0.7, 0.8, 0.8])
        img = img.resize(size=[s // 2 for s in img.size])       # half-size detection
        boxes *= 2                                                # scale boxes back
        p_h = h // 3, p_w = w // 3                              # 33% padding
    """
    
    def __init__(self, device: str = "cuda", verbose: bool = True):
        """
        Args:
            device: Device for face detection ("cuda" or "cpu")
            verbose: Whether to print status messages
        """
        if MTCNN is None:
            raise ImportError("facenet-pytorch not installed. Install with: pip install facenet-pytorch")
        
        self.device = device
        self.verbose = verbose
        # EXACT thresholds from training kernel_utils.py line 202
        self.detector = MTCNN(margin=0, thresholds=[0.7, 0.8, 0.8], device=device, keep_all=True)
        self._lock = threading.Lock()
    
    def extract_face(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extracts the most-confident face from a frame.
        Crop matches upstream kernel_utils.py; upstream keeps every face.

        Args:
            frame: RGB numpy array (H, W, 3), uint8
        
        Returns:
            RGB face crop (numpy array) or None if no face detected
        """
        try:
            h, w = frame.shape[:2]
            logger.debug(f"[extract_face] Frame shape: {frame.shape}, dtype: {frame.dtype}, "
                         f"R_mean: {frame[:,:,0].mean():.2f}, B_mean: {frame[:,:,2].mean():.2f}")

            # STEP 1: Detect on half-size image (matches training exactly)
            img = Image.fromarray(frame)
            half_img = img.resize([s // 2 for s in img.size])
            batch_boxes, probs = self.detector.detect(half_img, landmarks=False)

            if batch_boxes is None or len(batch_boxes) == 0:
                return None

            # STEP 2: Pick best face (highest probability)
            best_idx = int(np.argmax(probs))
            bbox = batch_boxes[best_idx]
            if bbox is None:
                return None

            # STEP 3: Scale box back to full resolution (boxes were from half-size)
            xmin, ymin, xmax, ymax = [int(b * 2) for b in bbox]
            bw = xmax - xmin
            bh = ymax - ymin

            # STEP 4: Add padding exactly as training does (h//3, w//3 of bbox)
            p_h = bh // 3
            p_w = bw // 3
            x1 = max(xmin - p_w, 0)
            y1 = max(ymin - p_h, 0)
            x2 = min(xmax + p_w, w)
            y2 = min(ymax + p_h, h)

            face = frame[y1:y2, x1:x2]

            if face.size == 0:
                return None

            return face

        except Exception as e:
            if self.verbose:
                logger.warning(f"[extract_face] Face detection error: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Inference Utilities
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VideoDetectionResult:
    """Results from video deepfake detection."""
    
    label: str  # "REAL", "FAKE", "UNSURE", "UNKNOWN" or "ERROR"
    predicted_class: int  # 0 = FAKE, 1 = REAL
    fake_prob: float
    real_prob: float
    confidence_pct: float
    device: str
    num_frames_processed: int
    frame_predictions: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def confident_strategy(predictions: List[float], threshold: float = 0.8) -> float:
    """
    Aggregate per-face P(fake) scores (upstream kernel_utils.py, unchanged).
    
    Returns average of high-confidence predictions if most frames agree,
    otherwise returns overall average.
    
    Args:
        predictions: List of frame-level prediction scores [0, 1]
        threshold: Confidence threshold for selecting predictions
    
    Returns:
        Aggregated prediction score
    """
    pred_array = np.array(predictions)
    num_frames = len(pred_array)
    
    # Count confident fake predictions
    confident_fakes = np.count_nonzero(pred_array > threshold)
    
    # If enough frames have high confidence fake, return average of those
    if confident_fakes > num_frames // 2.5 and confident_fakes > 11:
        return float(np.mean(pred_array[pred_array > threshold]))
    
    # If most frames are confidently real
    elif np.count_nonzero(pred_array < 0.2) > 0.9 * num_frames:
        return float(np.mean(pred_array[pred_array < 0.2]))
    
    # Otherwise return simple average
    else:
        return float(np.mean(pred_array))


def _isotropically_resize(img: np.ndarray, size: int) -> np.ndarray:
    """
    Resize image so the largest side equals `size`, keeping aspect ratio.
    Matches upstream kernel_utils.py:isotropically_resize_image
    """
    h, w = img.shape[:2]
    if max(w, h) == size:
        return img
    if w > h:
        scale = size / w
        new_h = int(h * scale)
        new_w = size
    else:
        scale = size / h
        new_w = int(w * scale)
        new_h = size
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    return cv2.resize(img, (new_w, new_h), interpolation=interpolation)


def _put_to_center(img: np.ndarray, input_size: int) -> np.ndarray:
    """
    Crop to input_size then zero-pad into a centered square, as in
    upstream kernel_utils.py:put_to_center
    """
    img = img[:input_size, :input_size]
    canvas = np.zeros((input_size, input_size, 3), dtype=np.uint8)
    start_w = (input_size - img.shape[1]) // 2
    start_h = (input_size - img.shape[0]) // 2
    canvas[start_h:start_h + img.shape[0], start_w:start_w + img.shape[1]] = img
    return canvas


def preprocess_frame(
    frame: np.ndarray,
    target_size: int = 380,
    normalize: bool = True
) -> torch.Tensor:
    """
    Preprocess a face crop for model inference.

    Matches the preprocessing in upstream kernel_utils.py:predict_on_video:
        resized_face = isotropically_resize_image(face, input_size)
        resized_face = put_to_center(resized_face, input_size)
        x[n] = resized_face
        x = x.permute((0, 3, 1, 2))
        x[i] = normalize_transform(x[i] / 255.)

    Args:
        frame: RGB face crop (numpy array, uint8)
        target_size: Target frame size (must match training input_size=380)
        normalize: Whether to apply ImageNet normalization

    Returns:
        Preprocessed tensor (C, H, W)
    """
    # Replicate training preprocessing exactly
    frame = _isotropically_resize(frame, target_size)
    frame = _put_to_center(frame, target_size)

    # Convert to tensor exactly as training does: permute then / 255
    tensor = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0

    if normalize:
        tensor = normalize_transform(tensor)

    return tensor


# ─────────────────────────────────────────────────────────────────────────────
# Model Loading
# ─────────────────────────────────────────────────────────────────────────────

_model_cache = {}
_cache_lock = threading.Lock()

_face_extractor_cache = {}
_face_extractor_lock = threading.Lock()

def get_face_extractor(device: str) -> 'FaceDetectionEngine':
    """
    Get or create a FaceDetectionEngine singleton for the given device.
    NOTE: If MTCNN settings change, call invalidate_caches() to rebuild.
    """
    with _face_extractor_lock:
        if device not in _face_extractor_cache:
            logger.info(f"[cache] Creating new FaceDetectionEngine for device={device} "
                        f"with thresholds=[0.7, 0.8, 0.8] (training-matched)")
            _face_extractor_cache[device] = FaceDetectionEngine(device=device, verbose=False)
        return _face_extractor_cache[device]


def invalidate_caches():
    """Clear all model and face extractor caches. Call this if settings change."""
    with _cache_lock:
        _model_cache.clear()
    with _face_extractor_lock:
        _face_extractor_cache.clear()
    logger.info("[cache] All model and face extractor caches cleared.")


def load_model(
    model_path: str,
    encoder: str = "tf_efficientnet_b7_ns",
    device: Optional[str] = None
) -> nn.Module:
    """
    Load a deepfake classifier model.
    
    Args:
        model_path: Path to model checkpoint
        encoder: Encoder architecture name
        device: Device to load model on ("cuda" or "cpu")
    
    Returns:
        Loaded model in eval mode
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # One cached instance per (weights, encoder, device), loaded under the lock
    # so concurrent first requests do not each read the multi-GB checkpoint.
    cache_key = (os.path.abspath(model_path), encoder, device)
    with _cache_lock:
        cached = _model_cache.get(cache_key)
        if cached is not None:
            return cached

        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Video model weights not found: {model_path}")

        model = DeepFakeClassifier(encoder=encoder)

        # The checkpoint pickles a few NumPy scalars (e.g. 'bce_best') under their
        # NumPy 1.x names; NumPy 2 moved them to numpy._core, so allow-list them
        # by their old name to keep the safe weights_only loader working.
        np_core = getattr(np, "_core", None) or np.core
        safe_globals = [
            (np_core.multiarray.scalar, "numpy.core.multiarray.scalar"),
            np.dtype,
            type(np.dtype("float64")),
        ]

        try:
            with torch.serialization.safe_globals(safe_globals):
                checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        except Exception as e:
            logger.warning(f"[load_model] Safe load failed ({e}); retrying with weights_only=False.")
            checkpoint = torch.load(model_path, map_location=device, weights_only=False)

        # Handle different checkpoint formats
        if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
            # Remove 'module.' prefix if present (from DataParallel)
            state_dict = {k.replace('module.', ''): v for k, v in checkpoint['state_dict'].items()}
        else:
            state_dict = checkpoint

        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            logger.warning(f"[load_model] {len(missing)} weights missing from checkpoint "
                           f"(left at random init), e.g. {missing[:3]}")
        if unexpected:
            logger.warning(f"[load_model] {len(unexpected)} unexpected checkpoint keys ignored, "
                           f"e.g. {unexpected[:3]}")

        model = model.to(device).eval()
        _model_cache[cache_key] = model
        logger.info(f"[load_model] Loaded {os.path.basename(model_path)} ({encoder}) on {device}")
        return model


def is_model_loaded(model_path: str) -> bool:
    """True once load_model() has cached these weights on any device."""
    path = os.path.abspath(model_path)
    with _cache_lock:
        return any(key[0] == path for key in _model_cache)


# ─────────────────────────────────────────────────────────────────────────────
# Detection Functions
# ─────────────────────────────────────────────────────────────────────────────

def detect_video_frames(
    frames: List[np.ndarray],
    model_path: str,
    encoder: str = "tf_efficientnet_b7_ns",
    device: Optional[str] = None,
    extract_faces: bool = True,
    target_size: int = 380,
    batch_size: int = 8
) -> VideoDetectionResult:
    """
    Detect deepfakes in a list of frames.
    
    Args:
        frames: List of RGB numpy arrays
        model_path: Path to model checkpoint
        encoder: Encoder architecture name
        device: Computation device
        extract_faces: Whether to extract faces before classification
        target_size: Target frame size for model
        batch_size: Faces per forward pass. 8 keeps peak RAM ~1.7 GB on CPU
            (32 peaks at ~4 GB) with the same throughput and identical outputs.
    
    Returns:
        VideoDetectionResult with predictions
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if not frames:
        return VideoDetectionResult(
            label="UNKNOWN", predicted_class=-1, fake_prob=0, real_prob=0,
            confidence_pct=0, device=device, num_frames_processed=0,
            notes=["No frames provided"]
        )
    
    # Load model
    model = load_model(model_path, encoder, device)
    
    # Extract faces if needed
    notes = []
    if extract_faces:
        face_extractor = get_face_extractor(device)
        extracted_frames = []
        for frame in frames:
            face = face_extractor.extract_face(frame)
            if face is not None:
                extracted_frames.append(face)
        
        if not extracted_frames:
            logger.warning(f"[detect_video] No faces found in any of {len(frames)} frames → returning UNSURE")
            return VideoDetectionResult(
                label="UNSURE", predicted_class=-1, fake_prob=0.5, real_prob=0.5,
                confidence_pct=50.0, device=device, num_frames_processed=len(frames),
                notes=["NO_FACE_DETECTED"]
            )
            
        if len(extracted_frames) == 1:
            logger.warning(f"[detect_video] Face detected in only 1 of {len(frames)} frames. Classifying using single frame.")
        
        logger.info(f"[detect_video] Frames sampled: {len(frames)}, Faces extracted: {len(extracted_frames)}")
        frames = extracted_frames
    
    # Preprocess frames
    preprocessed = []
    for frame in frames:
        try:
            tensor = preprocess_frame(frame, target_size, normalize=True)
            preprocessed.append(tensor)
        except Exception as e:
            logger.warning(f"[detect_video] Skipping frame that failed preprocessing: {e}")
            continue
    
    if not preprocessed:
        return VideoDetectionResult(
            label="UNKNOWN", predicted_class=-1, fake_prob=0, real_prob=0,
            confidence_pct=0, device=device, num_frames_processed=0,
            notes=["Failed to preprocess frames"]
        )
    
    # Inference
    frame_predictions = []
    with torch.no_grad():
        for i in range(0, len(preprocessed), batch_size):
            batch = torch.stack(preprocessed[i:i+batch_size]).to(device)
            logits = model(batch)
            probs = torch.sigmoid(logits).cpu().numpy().flatten()
            frame_predictions.extend(probs.tolist())
    
    # Aggregate predictions
    aggregated_score = confident_strategy(frame_predictions)
    fake_prob = aggregated_score
    real_prob = 1.0 - aggregated_score
    
    predicted_class = 1 if real_prob > 0.5 else 0
    label = "REAL" if predicted_class == 1 else "FAKE"
    confidence_pct = max(fake_prob, real_prob) * 100
    
    logger.info(f"[classify] Label={label}, RealProb={real_prob:.4f}, "
                f"FakeProb={fake_prob:.4f}, Confidence={confidence_pct:.4f}")
    
    return VideoDetectionResult(
        label=label,
        predicted_class=predicted_class,
        fake_prob=fake_prob,
        real_prob=real_prob,
        confidence_pct=confidence_pct,
        device=device,
        num_frames_processed=len(frames),
        frame_predictions=frame_predictions,
        notes=notes
    )


def detect_video_file(
    video_path: str,
    model_path: str,
    encoder: str = "tf_efficientnet_b7_ns",
    device: Optional[str] = None,
    num_frames: int = 32,
    extract_faces: bool = True,
    target_size: int = 380
) -> VideoDetectionResult:
    """
    Detect deepfakes in a video file.
    
    Args:
        video_path: Path to video file
        model_path: Path to model checkpoint
        encoder: Encoder architecture name
        device: Computation device
        num_frames: Number of frames to extract
        extract_faces: Whether to extract faces
        target_size: Target frame size
    
    Returns:
        VideoDetectionResult with predictions
    """
    if not os.path.exists(video_path):
        return VideoDetectionResult(
            label="ERROR", predicted_class=-1, fake_prob=0, real_prob=0,
            confidence_pct=0, device=device or "cpu", num_frames_processed=0,
            notes=[f"Video file not found: {video_path}"]
        )
    
    # Extract frames
    reader = VideoReader(verbose=False)
    frames = reader.read_frames(video_path, num_frames)
    
    if frames is None:
        return VideoDetectionResult(
            label="ERROR", predicted_class=-1, fake_prob=0, real_prob=0,
            confidence_pct=0, device=device or "cpu", num_frames_processed=0,
            notes=["Failed to read video frames"]
        )
    
    # Convert BGR to RGB
    frames = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
    
    return detect_video_frames(
        frames, model_path, encoder, device,
        extract_faces=extract_faces, target_size=target_size
    )

"""
ml_core/image_model/imd.py
==========================
Image Manipulation Detection pipeline.

Two-level analysis (mirrors the upstream z1311/Image-Manipulation-Detection repo):

  Level 1 — Metadata analysis
      Checks EXIF data for software signatures that indicate editing.

  Level 2 — Error Level Analysis (ELA) + CNN
      Re-saves the image at reduced JPEG quality and measures the difference
      (ELA image).  The ELA output is fed into a small CNN (IMDModel) that
      was trained on the CASIA tampered-image dataset.
      Class indices: 0 = Tampered, 1 = Authentic.

Public entry-points
-------------------
  load_model(model_path, device=None)         -> nn.Module  (cached)
  detect_image_file(image_path, model_path)   -> ImageDetectionResult
  detect_image_bytes(raw_bytes, model_path)   -> ImageDetectionResult
"""

from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image, ImageChops
from PIL.ExifTags import TAGS
from torch import nn


# ─────────────────────────────────────────────────────────────────────────────
# Model Architecture  (faithful reproduction of upstream model.py)
# ─────────────────────────────────────────────────────────────────────────────

class IMDModel(nn.Module):
    """
    Small CNN for image-manipulation detection trained on the CASIA dataset.

    Input:  ELA image resized to 128×128, normalised to [0, 1].
    Output: Softmax probabilities over two classes.
      - index 0: Tampered
      - index 1: Authentic
    """

    def __init__(self) -> None:
        super().__init__()
        maxpool = nn.MaxPool2d(kernel_size=2)
        relu = nn.ReLU()
        self.down_conv1 = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3),
            nn.BatchNorm2d(64),
            maxpool,
            relu,
        )
        self.down_conv2 = nn.Sequential(
            nn.Conv2d(in_channels=64, out_channels=16, kernel_size=3),
            nn.BatchNorm2d(16),
            maxpool,
            relu,
        )
        self.linear = nn.Sequential(
            nn.Linear(in_features=16 * 30 * 30, out_features=1024),
            nn.BatchNorm1d(1024),
            relu,
            nn.Linear(in_features=1024, out_features=64),
            nn.BatchNorm1d(64),
            relu,
            nn.Linear(in_features=64, out_features=2),
            nn.Softmax(dim=1),
        )

    def forward(self, img: torch.Tensor) -> torch.Tensor:
        d1 = self.down_conv1(img)
        d2 = self.down_conv2(d1)
        d2 = d2.view(-1, d2.shape[1] * d2.shape[2] * d2.shape[3])
        return self.linear(d2)


# ─────────────────────────────────────────────────────────────────────────────
# Result Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ImageDetectionResult:
    """
    Structured result returned by detect_image_file / detect_image_bytes.

    Attributes
    ----------
    label               : "AUTHENTIC" or "TAMPERED"
    predicted_class     : int — 1 = Authentic, 0 = Tampered
    authentic_prob      : float in [0, 1]
    tampered_prob       : float in [0, 1]
    device              : "cpu" or "cuda"
    software_found      : bool — True when EXIF software tag detected (Level 1)
    software_signature  : str  — Software name from EXIF, or "" if not found
    level1_notes        : list of human-readable findings from metadata scan
    """

    label: str
    predicted_class: int
    authentic_prob: float
    tampered_prob: float
    device: str
    software_found: bool = False
    software_signature: str = ""
    level1_notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "predicted_class": int(self.predicted_class),
            "authentic_prob": round(float(self.authentic_prob), 4),
            "tampered_prob": round(float(self.tampered_prob), 4),
            "confidence_pct": round(max(self.authentic_prob, self.tampered_prob) * 100, 2),
            "device": self.device,
            "level1": {
                "software_found": self.software_found,
                "software_signature": self.software_signature,
                "notes": list(self.level1_notes),
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Thread-safe model cache
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_LOCK: threading.Lock = threading.Lock()
_MODEL_CACHE: Dict[Tuple[str, str], nn.Module] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Device selection
# ─────────────────────────────────────────────────────────────────────────────

def _select_device() -> torch.device:
    """Use GPU if available, fall back to CPU safely."""
    try:
        if torch.cuda.is_available():
            print("[IMD] GPU detected — using CUDA for image inference.")
            return torch.device("cuda")
    except Exception as exc:
        print(f"[IMD] CUDA check failed ({exc}), falling back to CPU.")
    return torch.device("cpu")


# ─────────────────────────────────────────────────────────────────────────────
# Level 1 — Metadata analysis
# ─────────────────────────────────────────────────────────────────────────────

def _analyse_metadata(img: Image.Image) -> Tuple[bool, str, List[str]]:
    """
    Inspect EXIF tags for software signatures.

    Returns
    -------
    (software_found, software_value, notes)
    """
    notes: List[str] = []
    software_found = False
    software_value = ""

    try:
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if exif_data is None:
            notes.append("No EXIF data found.")
            return software_found, software_value, notes

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_name == "Software":
                software_found = True
                software_value = str(value).strip()
                notes.append(f"Software signature found: {software_value}")
                break

        if not software_found:
            notes.append("No software signature in EXIF — metadata looks clean.")

    except AttributeError:
        # PNG, BMP, etc. have no _getexif()
        notes.append("Image format does not support EXIF metadata.")
    except Exception as exc:
        notes.append(f"Metadata scan failed: {exc}")

    return software_found, software_value, notes


# ─────────────────────────────────────────────────────────────────────────────
# Level 2 — ELA preprocessing (vectorized, no pixel loop)
# ─────────────────────────────────────────────────────────────────────────────

def _ela_image(original: Image.Image, jpeg_quality: int = 90, scale: int = 10) -> Image.Image:
    """
    In-memory Error Level Analysis (ELA).

    Re-saves the image at `jpeg_quality` and computes the pixel difference
    between the original and the re-saved version, scaled by `scale`.

    This is a vectorized replacement for the upstream pixel-by-pixel loop —
    typically 50–100× faster on realistic image sizes.
    """
    original = original.convert("RGB")
    buf = io.BytesIO()
    original.save(buf, format="JPEG", quality=int(jpeg_quality))
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")

    diff = ImageChops.difference(original, recompressed)

    # Vectorized scale: clip to [0, 255] after multiplication
    diff_arr = np.asarray(diff, dtype=np.int32)
    diff_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
    return Image.fromarray(diff_arr, mode="RGB")


def _preprocess(img: Image.Image) -> torch.Tensor:
    """Resize to 128×128 and normalise to [0, 1], returning (1, 3, 128, 128)."""
    img = img.resize((128, 128))
    arr = np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
    return torch.from_numpy(np.expand_dims(arr, axis=0))


# ─────────────────────────────────────────────────────────────────────────────
# Model loading (cached)
# ─────────────────────────────────────────────────────────────────────────────

def load_model(model_path: str, device: Optional[torch.device] = None) -> nn.Module:
    """
    Load and cache the image manipulation detector model.

    Supports:
      - A pickled nn.Module  (``torch.load`` returns a Module directly)
      - A state-dict         (``torch.load`` returns a dict)

    Args:
        model_path : Absolute or relative path to the .pth weight file.
        device     : Target device; auto-selected if None.

    Returns:
        Loaded, eval-mode IMDModel on the target device.
    """
    import sys
    
    device = device or _select_device()
    abs_path = os.path.abspath(model_path)
    cache_key = (abs_path, device.type)

    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached is not None:
            return cached

        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Model weights not found: {abs_path}")

        # Ensure IMDModel is available in multiple namespaces for torch.load to find it
        # This fixes: "Can't get attribute 'IMDModel' on <module '__main__'..."
        import __main__
        __main__.IMDModel = IMDModel
        sys.modules['__main__'].IMDModel = IMDModel
        
        import numpy as np
        try:
            torch.serialization.add_safe_globals([np.core.multiarray.scalar])
        except AttributeError:
            pass

        try:
            payload = torch.load(abs_path, map_location=device, weights_only=True)
        except Exception as e:
            if "IMDModel" in str(e) or "can't get attribute" in str(e).lower():
                # Retry with explicit class registration
                __main__.IMDModel = IMDModel
                try:
                    payload = torch.load(abs_path, map_location=device, weights_only=True)
                except Exception:
                    payload = torch.load(abs_path, map_location=device, weights_only=False)
            else:
                print(f"Safe load failed: {e}. Retrying with weights_only=False.")
                payload = torch.load(abs_path, map_location=device, weights_only=False)

        if isinstance(payload, nn.Module):
            model = payload
        elif isinstance(payload, dict):
            model = IMDModel()
            state = payload.get("state_dict", payload)
            model.load_state_dict(state)
        else:
            raise TypeError(f"Unsupported model payload type: {type(payload)}")

        model.to(device)
        model.eval()
        _MODEL_CACHE[cache_key] = model
        print(f"[IMD] Model loaded from {abs_path} on {device.type.upper()}")
        return model


# ─────────────────────────────────────────────────────────────────────────────
# Core inference
# ─────────────────────────────────────────────────────────────────────────────

def _run_inference(pil_img: Image.Image, model_path: str,
                   device: Optional[torch.device] = None) -> ImageDetectionResult:
    """
    Shared inference logic used by both public entry-points.
    Runs Level 1 (metadata) and Level 2 (ELA + CNN).
    """
    device = device or _select_device()

    # Level 1 — metadata
    software_found, software_sig, notes = _analyse_metadata(pil_img)

    # Level 2 — ELA + CNN
    model = load_model(model_path=model_path, device=device)
    ela_img = _ela_image(pil_img)
    x = _preprocess(ela_img).to(device)

    with torch.no_grad():
        out = model(x)  # shape: (1, 2)

        # Guard: normalise if not already a probability distribution
        if not torch.allclose(out.sum(dim=1),
                              torch.ones_like(out.sum(dim=1)), atol=1e-3):
            out = torch.softmax(out, dim=1)

        probs = out.squeeze(0).detach().float().cpu()

    tampered_prob = float(probs[0].item())
    authentic_prob = float(probs[1].item())
    predicted_class = int(torch.argmax(probs).item())
    label = "AUTHENTIC" if predicted_class == 1 else "TAMPERED"

    print(f"[IMD] Result: {label}  "
          f"(authentic={authentic_prob:.3f}, tampered={tampered_prob:.3f})")

    return ImageDetectionResult(
        label=label,
        predicted_class=predicted_class,
        authentic_prob=authentic_prob,
        tampered_prob=tampered_prob,
        device=device.type,
        software_found=software_found,
        software_signature=software_sig,
        level1_notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def detect_image_file(
    image_path: str,
    model_path: str,
    device: Optional[torch.device] = None,
) -> ImageDetectionResult:
    """
    Analyse an image file on disk.

    Args:
        image_path : Path to the image file (.jpg, .png, .bmp, etc.)
        model_path : Path to the IMDModel weights (.pth)
        device     : Optional target device; auto-selected if None.

    Returns:
        ImageDetectionResult with Level-1 and Level-2 findings.
    """
    pil_img = Image.open(image_path).convert("RGB")
    return _run_inference(pil_img, model_path=model_path, device=device)


def detect_image_bytes(
    raw_bytes: bytes,
    model_path: str,
    device: Optional[torch.device] = None,
) -> ImageDetectionResult:
    """
    Analyse an image provided as raw bytes (e.g. from Django request.FILES).

    Args:
        raw_bytes  : Image data as a bytes object.
        model_path : Path to the IMDModel weights (.pth)
        device     : Optional target device; auto-selected if None.

    Returns:
        ImageDetectionResult with Level-1 and Level-2 findings.
    """
    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    return _run_inference(pil_img, model_path=model_path, device=device)

"""
core/pipeline/ela.py
====================
Error Level Analysis: the single implementation used by the service, the
evaluation harness (scripts/eval_image.py) and any future training code, so
training and inference cannot drift apart (the audit could not verify that the
deployed model's training ELA matched inference: train.ipynb consumed ELA images
made by a script that is not in the repository).

    ela_image(img)             -> RGB image: |img - jpeg(img, q=90)| * 10, clipped
    to_model_input(ela)        -> (1, 3, 128, 128) float tensor in [0, 1]
    mean_ela(img)              -> float: the mean-intensity baseline (no model)
"""

from __future__ import annotations

import io

import numpy as np
import torch
from PIL import Image, ImageChops

JPEG_QUALITY = 90
SCALE = 10
INPUT_SIZE = 128

# ELA is computed in horizontal strips so peak memory is one output buffer plus
# one strip, not several full-size copies. Strips start on the 16-row JPEG MCU
# grid and are re-encoded with a 16-row margin on each side, so chroma
# upsampling at strip edges sees the same neighbours as a whole-image encode:
# the result is bit-identical to whole-image ELA (tests/test_memory_bounds.py).
_ELA_STRIP_ROWS = 512
_ELA_MARGIN_ROWS = 16


def ela_image(original: Image.Image, jpeg_quality: int = JPEG_QUALITY, scale: int = SCALE) -> Image.Image:
    """
    In-memory Error Level Analysis (ELA) at native resolution.

    Re-saves the image at `jpeg_quality` and returns the per-pixel difference
    between the original and the re-saved version, multiplied by `scale` and
    clipped to 255. Everything stays uint8.
    """
    if original.mode != "RGB":
        original = original.convert("RGB")
    width, height = original.size
    out = Image.new("RGB", (width, height))
    amplify = [min(255, value * scale) for value in range(256)] * 3  # per-band lookup table

    for top in range(0, height, _ELA_STRIP_ROWS):
        bottom = min(top + _ELA_STRIP_ROWS, height)
        lo = max(0, top - _ELA_MARGIN_ROWS)
        hi = min(height, bottom + _ELA_MARGIN_ROWS)
        tile = original.crop((0, lo, width, hi))

        buf = io.BytesIO()
        tile.save(buf, format="JPEG", quality=int(jpeg_quality))
        buf.seek(0)
        recompressed = Image.open(buf, formats=("JPEG",)).convert("RGB")  # noqa: TID251 — our own re-encode

        diff = ImageChops.difference(tile, recompressed).point(amplify)
        out.paste(diff.crop((0, top - lo, width, bottom - lo)), (0, top))

    return out


def to_model_input(ela: Image.Image) -> torch.Tensor:
    """Resize to 128×128 and normalise to [0, 1], returning (1, 3, 128, 128)."""
    img = ela.resize((INPUT_SIZE, INPUT_SIZE))
    arr = np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
    return torch.from_numpy(np.expand_dims(arr, axis=0))


def mean_ela(img: Image.Image) -> float:
    """Baseline score with no model: mean ELA intensity in [0, 1].

    A trained model that cannot beat this one-line heuristic is not adding value.
    """
    return float(np.asarray(ela_image(img), dtype=np.float32).mean() / 255.0)

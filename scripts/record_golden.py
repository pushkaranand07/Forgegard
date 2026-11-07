"""
Record expected scores for the golden-sample regression tests.

    python scripts/record_golden.py --make-synthetic   # (re)create the synthetic image fixtures
    python scripts/record_golden.py                    # score every file in tests/golden/media/

Writes tests/golden/expected.json. Each entry stores the media file's SHA-256,
the weights' SHA-256 it was recorded with, the label and the score
(image: tampered_prob, video: fake_prob or null). tests/test_golden.py then
asserts the live pipeline reproduces them within a tolerance.

Only commit media you are allowed to publish. Clips from DFDC, Celeb-DF or
CASIA must NOT go in the repo (their licences forbid redistribution).

Re-record only after an intentional pipeline change, and say why in the commit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GOLDEN = os.path.join(ROOT, "tests", "golden")
MEDIA = os.path.join(GOLDEN, "media")
EXPECTED = os.path.join(GOLDEN, "expected.json")
WEIGHTS = os.path.join(ROOT, "weights")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXT = {".mp4", ".avi", ".webm", ".mov", ".mkv"}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_synthetic() -> None:
    """Deterministic, licence-free images that exercise the pipeline numerically.

    They are not realistic forgeries and say nothing about accuracy. They are
    chosen so the recorded scores spread from ~0 to 1 (a regression in the
    pipeline then moves at least some of them).
    """
    import numpy as np
    from PIL import Image, ImageFilter

    os.makedirs(MEDIA, exist_ok=True)
    for old in os.listdir(MEDIA):
        if old.startswith("synthetic_"):
            os.remove(os.path.join(MEDIA, old))

    yy, xx = np.mgrid[0:256, 0:320]
    gradient = np.stack([(xx * 0.7) % 256, (yy * 0.9) % 256, ((xx + yy) * 0.4) % 256], axis=-1)

    def noisy(sigma: float, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return np.clip(gradient + rng.normal(0, sigma, gradient.shape), 0, 255).astype(np.uint8)

    def save(arr, name, blur=0, **kw):
        img = Image.fromarray(arr)
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        img.save(os.path.join(MEDIA, name), **kw)

    save(noisy(0, 1), "synthetic_smooth_q90.jpg", quality=90)
    save(noisy(3, 2), "synthetic_noise3_q95.jpg", quality=95)
    save(noisy(12, 3), "synthetic_noise12_q75.jpg", quality=75)
    save(noisy(12, 4), "synthetic_noise12_q90.jpg", quality=90)
    save(noisy(12, 5), "synthetic_noise12_q95_blur2.jpg", blur=2, quality=95)
    save(noisy(12, 6), "synthetic_noise12.png")

    # "Spliced": a patch with a different JPEG history pasted into a smooth image
    rng = np.random.default_rng(7)
    patch = np.clip(rng.normal(128, 50, (96, 96, 3)), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(patch).save(buf, format="JPEG", quality=55)
    spliced = noisy(0, 1).copy()
    spliced[80:176, 120:216] = np.asarray(Image.open(buf).convert("RGB"))
    save(spliced, "synthetic_spliced_q90.jpg", quality=90)
    print(f"Wrote synthetic images to {MEDIA}")


def record() -> int:
    import torch

    from core.pipeline import image_processor, video_processor

    image_w = os.path.join(WEIGHTS, "model_c1.pth")
    video_w = os.path.join(WEIGHTS, "deepfake_detector_b7.pth")
    entries = {}
    for name in sorted(os.listdir(MEDIA)):
        path = os.path.join(MEDIA, name)
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXT:
            r = image_processor.detect_image_file(path, image_w, torch.device("cpu"))
            entries[name] = {"kind": "image", "label": r.label, "score": round(r.tampered_prob, 6),
                             "weights_sha256": sha256(image_w)}
        elif ext in VIDEO_EXT:
            r = video_processor.detect_video_file(path, video_w, device="cpu")
            score = None if r.fake_prob is None else round(r.fake_prob, 6)
            entries[name] = {"kind": "video", "label": r.label, "score": score,
                             "weights_sha256": sha256(video_w)}
        else:
            continue
        entries[name]["media_sha256"] = sha256(path)
        print(f"{name}: {entries[name]['label']} score={entries[name]['score']}")

    with open(EXPECTED, "w", encoding="utf-8") as f:
        json.dump({"tolerance": 0.02, "device": "cpu", "samples": entries}, f, indent=2)
        f.write("\n")
    print(f"Wrote {EXPECTED}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--make-synthetic", action="store_true", help="create synthetic image fixtures first")
    args = parser.parse_args()
    if args.make_synthetic:
        make_synthetic()
    return record()


if __name__ == "__main__":
    raise SystemExit(main())

"""
I5: memory per request must not scale with how large an upload decodes to.

The audit measured +2.5 GB RSS for one 10 MB, 49 MP JPEG and +2.7 GB for one
4 MB, 4096x4096 AVI. Each case runs in a fresh subprocess so the measurement is
not polluted by the test runner. Peak growth is measured conservatively:
(process lifetime peak after the call) - (RSS just before the call).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageChops

from core.pipeline import image_processor

ROOT = Path(__file__).resolve().parent.parent
BUDGET_MB = 600

pytestmark = pytest.mark.memory


# ── ELA exactness: strip processing must equal whole-image ELA ────────────────

def _reference_ela(original: Image.Image, jpeg_quality: int = 90, scale: int = 10) -> np.ndarray:
    """The pre-I5 whole-image implementation, kept verbatim as the oracle."""
    original = original.convert("RGB")
    buf = io.BytesIO()
    original.save(buf, format="JPEG", quality=int(jpeg_quality))
    buf.seek(0)
    recompressed = Image.open(buf, formats=("JPEG",)).convert("RGB")  # noqa: TID251 — own buffer
    diff = np.asarray(ImageChops.difference(original, recompressed), dtype=np.int32)
    return np.clip(diff * scale, 0, 255).astype(np.uint8)


def _jpeg_roundtrip(arr: np.ndarray, quality: int) -> Image.Image:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=quality)
    return Image.open(io.BytesIO(buf.getvalue()), formats=("JPEG",))  # noqa: TID251 — own buffer


@pytest.mark.parametrize("height,width", [(333, 517), (1200, 800), (1601, 97), (16, 16), (2050, 1030)])
def test_strip_ela_is_bit_identical_to_whole_image_ela(height, width):
    rng = np.random.default_rng(height * width)
    smooth = cv2.resize(rng.integers(0, 255, (max(height // 16, 2), max(width // 16, 2), 3), dtype=np.uint8),
                        (width, height), interpolation=cv2.INTER_CUBIC)
    noisy = np.clip(smooth.astype(np.int16) + rng.integers(-20, 20, smooth.shape), 0, 255).astype(np.uint8)
    for img in (Image.fromarray(noisy), _jpeg_roundtrip(noisy, 75), Image.fromarray(noisy).convert("L")):
        expected = _reference_ela(img)
        actual = np.asarray(image_processor._ela_image(img))
        assert actual.shape == expected.shape
        assert np.array_equal(actual, expected), f"max diff {np.abs(actual.astype(int) - expected).max()}"


def test_strip_ela_matches_on_golden_media():
    media = ROOT / "tests" / "golden" / "media"
    for path in sorted(media.glob("*")):
        with Image.open(path) as img:  # noqa: TID251 — committed fixture
            img.load()
            assert np.array_equal(np.asarray(image_processor._ela_image(img)), _reference_ela(img)), path.name


# ── RSS bounds, measured in a subprocess ─────────────────────────────────────

_HARNESS = textwrap.dedent(
    """
    import json, os, sys, threading, time
    import psutil
    sys.path.insert(0, os.environ["FG_ROOT"])
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    proc = psutil.Process()

    def lifetime_peak():
        info = proc.memory_info()
        if hasattr(info, "peak_wset"):
            return info.peak_wset
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    peak = [0]
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], proc.memory_info().rss)
            time.sleep(0.002)

    kind, path, weights = sys.argv[1], sys.argv[2], sys.argv[3]
    import torch
    torch.set_num_threads(2)
    if kind == "image":
        from core.pipeline import image_processor
        data = open(path, "rb").read()
        image_processor.load_model(weights, torch.device("cpu"))
        run = lambda: image_processor.detect_image_bytes(data, weights, torch.device("cpu"), extension="jpg")
    else:
        from core.pipeline import video_processor
        video_processor.load_model = lambda *a, **k: object()   # classifier is not under test
        video_processor.get_face_extractor("cpu")                # load MTCNN before measuring
        run = lambda: video_processor.detect_video_file(path, "unused.pth", device="cpu")

    before = proc.memory_info().rss
    t = threading.Thread(target=sample, daemon=True); t.start()
    result = run()
    stop.set(); t.join()
    growth = max(peak[0], lifetime_peak()) - before
    print(json.dumps({"growth_mb": growth / 1048576, "label": getattr(result, "label", None)}))
    """
)


def _peak_growth_mb(tmp_path: Path, kind: str, media: Path, weights: Path) -> dict:
    script = tmp_path / "harness.py"
    script.write_text(_HARNESS, encoding="utf-8")
    env = {**os.environ, "FG_ROOT": str(ROOT), "FORGEGUARD_VERIFY_WEIGHTS": "false"}
    out = subprocess.run([sys.executable, str(script), kind, str(media), str(weights)],
                         capture_output=True, text=True, env=env, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    result = json.loads(out.stdout.strip().splitlines()[-1])
    print(f"{kind} {media.name}: peak RSS growth {result['growth_mb']:.0f} MB (budget {BUDGET_MB} MB)")
    return result


@pytest.fixture(scope="module")
def tiny_imd_weights(tmp_path_factory) -> Path:
    import torch

    path = tmp_path_factory.mktemp("w") / "imd_test.pth"
    torch.save(image_processor.IMDModel().state_dict(), path)
    return path


def test_49_megapixel_jpeg_stays_within_budget(tmp_path, tiny_imd_weights):
    rng = np.random.default_rng(0)
    pixels = cv2.resize(rng.integers(0, 255, (700, 700, 3), dtype=np.uint8), (7000, 7000))
    media = tmp_path / "49mp.jpg"
    Image.fromarray(pixels).save(media, format="JPEG", quality=85)
    del pixels

    result = _peak_growth_mb(tmp_path, "image", media, tiny_imd_weights)

    assert result["label"] in {"AUTHENTIC", "TAMPERED"}
    assert result["growth_mb"] < BUDGET_MB, f"peak RSS growth {result['growth_mb']:.0f} MB"


def test_4096_square_video_stays_within_budget(tmp_path):
    media = tmp_path / "huge.avi"
    writer = cv2.VideoWriter(str(media), cv2.VideoWriter_fourcc(*"MJPG"), 10, (4096, 4096))
    for i in range(40):
        writer.write(np.full((4096, 4096, 3), i, np.uint8))
    writer.release()

    result = _peak_growth_mb(tmp_path, "video", media, Path("unused.pth"))

    assert result["label"] == "UNSURE"  # flat frames: no face
    assert result["growth_mb"] < BUDGET_MB, f"peak RSS growth {result['growth_mb']:.0f} MB"


def test_video_above_resolution_cap_is_rejected_before_decoding(tmp_path):
    from core.pipeline.video_processor import InvalidFileException, VideoReader

    media = tmp_path / "too_big.avi"
    writer = cv2.VideoWriter(str(media), cv2.VideoWriter_fourcc(*"MJPG"), 10, (4112, 4112))
    writer.write(np.zeros((4112, 4112, 3), np.uint8))
    writer.release()

    with pytest.raises(InvalidFileException, match="resolution"):
        VideoReader(verbose=False).iter_frames(str(media), 4)


def test_frames_above_1920_are_downscaled_and_smaller_ones_untouched(tmp_path):
    from core.pipeline.video_processor import VideoReader

    sizes = {}
    for w, h in [(2560, 1440), (1280, 720)]:
        media = tmp_path / f"{w}.avi"
        writer = cv2.VideoWriter(str(media), cv2.VideoWriter_fourcc(*"MJPG"), 10, (w, h))
        for _ in range(4):
            writer.write(np.zeros((h, w, 3), np.uint8))
        writer.release()
        sizes[w] = [f.shape for f in VideoReader(verbose=False).iter_frames(str(media), 2)]
    assert sizes[2560] == [(1080, 1920, 3)] * 2
    assert sizes[1280] == [(720, 1280, 3)] * 2

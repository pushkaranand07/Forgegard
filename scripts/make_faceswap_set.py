"""
Build paired real / face-swapped test clips from a folder of real videos.

    python scripts/make_faceswap_set.py --videos path/to/real_videos --out eval/data/faceswap

For each input video, two 120-frame segments (starting 5% and 55% in) are written
as-is (label 0) and with every face replaced by the largest face from the next
video (label 1): MTCNN finds the face, the donor face is resized to the box and
blended with an elliptical mask (cv2.seamlessClone). This is the audit's recipe:
a crude, visible swap, much easier than DFDC/Celeb-DF fakes, so results on it are
an upper bound, not a benchmark. Videos with no detectable face are skipped.

Writes the clips plus labels.csv (file, label, source, start_frame). Bring your
own videos: none are shipped, because test footage of real people is not ours to
redistribute.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SEGMENT_FRAMES = 120
STARTS = (0.05, 0.55)
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _largest_face(detector, rgb: np.ndarray):
    boxes, _ = detector.detect(Image.fromarray(rgb))
    if boxes is None:
        return None
    x1, y1, x2, y2 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    return [int(v) for v in (x1, y1, x2, y2)]


def _donor_face(detector, path: Path):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for frac in (0.1, 0.3, 0.5, 0.7):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * frac))
        ok, bgr = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        box = _largest_face(detector, rgb)
        if box:
            x1, y1, x2, y2 = box
            return bgr[max(y1, 0):y2, max(x1, 0):x2]
    return None


def _swap(frame_bgr: np.ndarray, box, donor_bgr: np.ndarray) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = max(box[0], 1), max(box[1], 1), min(box[2], w - 2), min(box[3], h - 2)
    bw, bh = x2 - x1, y2 - y1
    if bw <= 20 or bh <= 20:
        return frame_bgr
    src = cv2.resize(donor_bgr, (bw, bh))
    mask = np.zeros((bh, bw), np.uint8)
    cv2.ellipse(mask, (bw // 2, bh // 2), (int(bw * 0.42), int(bh * 0.48)), 0, 0, 360, 255, -1)
    try:
        return cv2.seamlessClone(src, frame_bgr, mask, (x1 + bw // 2, y1 + bh // 2), cv2.NORMAL_CLONE)
    except cv2.error:
        return frame_bgr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("eval/data/faceswap"))
    args = parser.parse_args()

    from facenet_pytorch import MTCNN

    detector = MTCNN(keep_all=True, device="cpu", thresholds=[0.7, 0.8, 0.8])
    videos = sorted(p for p in args.videos.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if len(videos) < 2:
        raise SystemExit("Need at least two videos (each one donates a face to the next).")
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, src in enumerate(videos):
        donor = _donor_face(detector, videos[(i + 1) % len(videos)])
        if donor is None:
            print(f"skip {src.name}: no face in the donor video")
            continue
        cap = cv2.VideoCapture(str(src))
        n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 25
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        for s, frac in enumerate(STARTS):
            start = int(n * frac)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            names = (f"real_{i:02d}_{s}.mp4", f"swap_{i:02d}_{s}.mp4")
            writers = [cv2.VideoWriter(str(args.out / nm), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                       for nm in names]
            box = None
            for k in range(SEGMENT_FRAMES):
                ok, bgr = cap.read()
                if not ok:
                    break
                writers[0].write(bgr)
                if k % 2 == 0:  # re-detect every other frame
                    box = _largest_face(detector, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                writers[1].write(_swap(bgr, box, donor) if box else bgr)
            for wr in writers:
                wr.release()
            rows += [{"file": names[0], "label": 0, "source": src.name, "start_frame": start},
                     {"file": names[1], "label": 1, "source": src.name, "start_frame": start}]
        print(f"{src.name}: 2 real + 2 swapped segments")

    with (args.out / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "label", "source", "start_frame"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} clips and labels.csv to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

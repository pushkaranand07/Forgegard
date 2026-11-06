"""
One-off: convert the pickled IMDModel checkpoint to a plain state_dict.

train.ipynb saved the image model with ``torch.save(model, ...)``, which
pickles the whole object. Loading it requires ``weights_only=False``
(arbitrary code execution if the file were ever swapped) and a
``__main__.IMDModel`` monkeypatch. This script does that unsafe load exactly
once, in a context you trust (your own file), checks that the re-saved
weights reproduce the original outputs bit for bit, and writes a
state_dict that loads with ``weights_only=True``.

Usage:
    python scripts/convert_imd_to_state_dict.py            # converts weights/model_c1.pth in place
    python scripts/convert_imd_to_state_dict.py --src a.pth --dst b.pth

In-place mode keeps the original as weights/model_c1.legacy-pickle.pth.
Afterwards, update core/model_manifest.json with the printed SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.pipeline.image_processor import IMDModel  # noqa: E402


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    default = os.path.join(ROOT, "weights", "model_c1.pth")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", default=default)
    parser.add_argument("--dst", default=default)
    args = parser.parse_args()

    src, dst = os.path.abspath(args.src), os.path.abspath(args.dst)
    if src == dst:
        backup = os.path.splitext(src)[0] + ".legacy-pickle.pth"
        if os.path.exists(backup):
            print(f"Refusing to overwrite existing backup {backup}", file=sys.stderr)
            return 1
        shutil.copy2(src, backup)
        src = backup
        print(f"Original kept at {backup}")

    # Trusted, one-off unsafe load: the pickle references __main__.IMDModel.
    import __main__
    __main__.IMDModel = IMDModel
    legacy = torch.load(src, map_location="cpu", weights_only=False)
    if isinstance(legacy, dict):
        print("Source is already a state_dict; nothing to convert.", file=sys.stderr)
        return 1
    legacy.eval()

    model = IMDModel()
    model.load_state_dict(legacy.state_dict(), strict=True)
    model.eval()

    x = torch.rand(8, 3, 128, 128, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        same = torch.equal(legacy(x), model(x))
    if not same:
        print("Converted model does not reproduce the original outputs; aborting.", file=sys.stderr)
        return 1

    torch.save(model.state_dict(), dst)
    torch.load(dst, map_location="cpu", weights_only=True)  # must load safely
    print(f"Wrote state_dict to {dst}")
    print(f"source sha256: {sha256(src)}")
    print(f"output sha256: {sha256(dst)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

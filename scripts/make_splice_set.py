"""
Build a reproducible, labelled image-splicing test set from the Kodak suite.

    python scripts/make_splice_set.py --out eval/data/kodak-splice

Source: the 24 lossless Kodak test images (http://r0k.us/graphics/kodak/), which the
site describes as released by Eastman Kodak for unrestricted use. They are downloaded
on first run and checked against pinned SHA-256 hashes; they are not stored in git.

Recipe (the one the November 2026 audit used, on public images instead):
for each base image i, with donor image (i + 1) mod 24 and a seeded random patch
of 180-320 px at a random position,

    auth_single_i     base saved once as JPEG q92                       label 0
    splice_single_i   patch pasted into the base, saved once as q92      label 1
    auth_double_i     base saved as q75, decoded, saved as q92           label 0
    splice_double_i   patch (from the lossless donor) pasted into the
                      q75-decoded base, saved as q92                     label 1

The double-compression pair is the textbook case for ELA. Output: the JPEGs plus
labels.csv (file, label, variant, base, donor, patch box). Same seed, same set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import random
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

KODAK_URL = "http://r0k.us/graphics/kodak/kodak/{name}"
KODAK_SHA256 = {
    "kodim01.png": "a56e27cbf5f843c048b6af1d6e090760e9c92fadba88b7dee0205918a37523bd",
    "kodim02.png": "4f4b74a79237e311d72cad958237b5f7088d8bce1c82305ebefe1a70e3022dfd",
    "kodim03.png": "e25ca1ff2f0c0cb5fdfd5f9b0a0bb21ac4c3de3c84a67f35b09a85d3306249db",
    "kodim04.png": "e3b946107c5d3441c022f678d0c3caf1e224d81b1604ba840a4f88e562de61aa",
    "kodim05.png": "10349e963c5c813d327852f82c1795fa4148d69fedffc4c589bee458e3ac3d53",
    "kodim06.png": "363510303b715d4cbc384e1ce227e466b613a09e1b71ae985882bf8e7fbd9b18",
    "kodim07.png": "b77d3f006f42414bb242222e0482e750c0fb9e5ee8d4bed2f6f11c5605fe54a4",
    "kodim08.png": "ba23983c76b4832ee0e8af0592664756841a16779acd69f792e268fb6d13d6e7",
    "kodim09.png": "6a4361c2fc194feb4edaa9f9a4a0620fb9943e460ac7fdf037fb0f6dd6607a7d",
    "kodim10.png": "9dfb70f5867c29ff9ed6313683f19b3d867849e40fbc0c4c54a4a89df341cf23",
    "kodim11.png": "7936814b58b5387fce2e4e2488b4ec830dadd95fa9520f358ddb30990b50f2b6",
    "kodim12.png": "d78c37c2f04f23761ed2367dd77e2db584ddd4c3950833fecf89f199a8126980",
    "kodim13.png": "bc34a3ce58dea09dce1704c997171602de90cb34d0c8503a988b77f473d39b08",
    "kodim14.png": "55a94550ff18f3246c4074fd32b77b0c74447c26b6ad274d564d999c0450ba6e",
    "kodim15.png": "7538cbb80cb9103606c48b806eae57d56c885c7f90b9b3be70a41160f9cbb683",
    "kodim16.png": "a89c7268ccd4718ba424a99fc4643c572cf692ca6eae887185ceb4e9f11d2e54",
    "kodim17.png": "37afcc89fbdcb76d9518e04b2fc011027e2f4cd14b3b2f83cefd721641a47c5b",
    "kodim18.png": "1a9258c365988961d87a0598725b609139c303ad48a5aad6c503c3b1a87849aa",
    "kodim19.png": "b7450b264b1b0a411390d8931b112c27905a992520fc90569dc4b920aa32bbdc",
    "kodim20.png": "3b46c71e3b92a563820ba32936be8330c586c41f938efd94be938386aae4328a",
    "kodim21.png": "ac958597c82073f6bb65129c68f72b651db5b9efd82e11547d07350214bc268b",
    "kodim22.png": "1cee58eb1f2d9c7ebb254d208a03c783ce6cf2c4d8c2cf45e235dd23b4ce1b29",
    "kodim23.png": "e3111a2fd4da24af15d6459ef9eacfe54106b38e27b4a21821b75c3f5d2d5baf",
    "kodim24.png": "1071c68372cc5a01435c2c225a5cf7d4bb803846ec08bb6b3d6721b156d7cb96"
}

PATCH_MIN, PATCH_MAX = 180, 320


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_kodak(cache: Path) -> list[Path]:
    """Download (once) and verify the 24 Kodak images."""
    cache.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, expected in sorted(KODAK_SHA256.items()):
        path = cache / name
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            with urllib.request.urlopen(KODAK_URL.format(name=name), timeout=60) as resp:  # noqa: S310
                data = resp.read()
            if sha256(data) != expected:
                raise SystemExit(f"{name}: downloaded file does not match the pinned SHA-256")
            path.write_bytes(data)
        paths.append(path)
    return paths


def jpeg_bytes(arr: np.ndarray, quality: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def decode(data: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(data), formats=("JPEG",)) as img:  # noqa: TID251 — our own buffer
        return np.asarray(img.convert("RGB"))


def build(sources: list[Path], out: Path, seed: int) -> int:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    images = []
    for p in sources:
        with Image.open(p, formats=("PNG",)) as img:  # noqa: TID251 — pinned fixture
            images.append(np.asarray(img.convert("RGB")))

    rows = []
    for i, base in enumerate(images):
        donor = images[(i + 1) % len(images)]
        size = rng.randint(PATCH_MIN, PATCH_MAX)
        sy, sx = rng.randint(0, donor.shape[0] - size), rng.randint(0, donor.shape[1] - size)
        ty, tx = rng.randint(0, base.shape[0] - size), rng.randint(0, base.shape[1] - size)
        patch = donor[sy:sy + size, sx:sx + size]
        box = f"{tx},{ty},{size}"

        previously_compressed = decode(jpeg_bytes(base, 75))
        variants = {
            "auth_single": (base, 0),
            "splice_single": (_paste(base, patch, ty, tx), 1),
            "auth_double": (previously_compressed, 0),
            "splice_double": (_paste(previously_compressed, patch, ty, tx), 1),
        }
        for variant, (arr, label) in variants.items():
            name = f"{variant}_{i:02d}.jpg"
            (out / name).write_bytes(jpeg_bytes(arr, 92))
            rows.append({"file": name, "label": label, "variant": variant,
                         "base": sources[i].name, "donor": sources[(i + 1) % len(sources)].name,
                         "patch_x_y_size": box if label else ""})

    with (out / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _paste(base: np.ndarray, patch: np.ndarray, y: int, x: int) -> np.ndarray:
    out = base.copy()
    out[y:y + patch.shape[0], x:x + patch.shape[1]] = patch
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("eval/data/kodak-splice"))
    parser.add_argument("--cache", type=Path, default=Path("eval/data/kodak-source"))
    parser.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    n = build(fetch_kodak(args.cache), args.out, args.seed)
    print(f"Wrote {n} images and labels.csv to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

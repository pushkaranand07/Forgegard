"""
Build the CASIA v2 evaluation/training set used by phase 3c.

    python scripts/prepare_casia.py --src eval/data/casia2-src --out eval/data/casia2

Source: the CASIA v2.0 shards in the Hugging Face dataset
ductai199x/image-manipulation-dataset-compilation (fetch the CASIA2.0-*.tar
shards and check them against their LFS SHA-256 first; nothing here downloads).
The images there are the original CASIA files re-saved losslessly as PNG, so
"Au_ani_00001.jpg.png" holds the decoded pixels of the original JPEG.

Two decisions keep the set honest:

* Only JPEG-origin images, in both classes. In CASIA v2, 99.3% of authentic
  images are JPEG but 60% of tampered ones are TIFF, so on the full set a model
  can score well by recognising the file format instead of the tampering. ELA
  is a JPEG technique and the service only scores JPEGs anyway.
* Split by source image. A tampered image is built from one or two authentic
  images (named in its file name: Tp_D_..._nat10139_nat00059_11949 uses
  Au_nat_10139 and Au_nat_00059). Every tampered image and its sources form a
  group (connected components), and whole groups go to train / val / test, so
  no picture's content is seen in training and again at test time.

Writes <out>/images/*.png and <out>/labels.csv with columns
file,label,split,group (label 1 = tampered). Deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

SEED = 20261108
SPLITS = (("train", 0.70), ("val", 0.15), ("test", 0.15))
AUTH = re.compile(r"^Au_([a-z]{3})_(\d{4,5})\.jpg\.png$")
TAMPERED = re.compile(r"^Tp_[DS]_[A-Z]{3}_[A-Z]_[A-Z]_([a-z]{3})(\d{5})_([a-z]{3})(\d{5})_\d{5}\.jpg\.png$")


def source_id(category: str, number: str) -> str:
    return f"{category}{int(number):05d}"


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)


def assign_splits(sizes: dict[str, tuple[int, int]], seed: int) -> dict[str, str]:
    """Stratified group split: whole groups, ~SPLITS fractions of each class per split.

    `sizes` maps group -> (authentic count, tampered count). Groups are visited
    largest first (ties broken by a seeded shuffle) and each goes to the split
    furthest below its target for the group's dominant class. Shared sources
    chain CASIA's tampered images into one component holding most of them; it
    is too big for val or test, so largest-first sends it to train.
    """
    order = sorted(sizes)
    random.Random(seed).shuffle(order)
    order.sort(key=lambda g: -sum(sizes[g]))  # stable: the shuffle breaks ties
    totals = [sum(s[c] for s in sizes.values()) for c in (0, 1)]
    filled = {name: [0, 0] for name, _ in SPLITS}
    out = {}
    for g in order:
        cls = 1 if sizes[g][1] else 0
        name = max(SPLITS, key=lambda s: s[1] * totals[cls] - filled[s[0]][cls])[0]
        out[g] = name
        filled[name][0] += sizes[g][0]
        filled[name][1] += sizes[g][1]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--src", type=Path, required=True, help="directory holding the CASIA2.0-*.tar shards")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    shards = sorted(args.src.glob("CASIA2.0-*.tar"))
    if not shards:
        print(f"No CASIA2.0-*.tar shards in {args.src}", file=sys.stderr)
        return 1
    images = args.out / "images"
    images.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []  # file, label, sources
    for shard in shards:
        with tarfile.open(shard) as tar:
            for member in tar:
                name = Path(member.name).name  # basename only: never trust archive paths
                if not member.isfile():
                    continue
                if m := AUTH.match(name):
                    label, sources = 0, [source_id(m[1], m[2])]
                elif m := TAMPERED.match(name):
                    label, sources = 1, [source_id(m[1], m[2]), source_id(m[3], m[4])]
                else:
                    continue  # non-JPEG origin, masks, metadata
                data = tar.extractfile(member)
                assert data is not None
                (images / name).write_bytes(data.read())
                rows.append({"file": f"images/{name}", "label": label, "sources": sources})

    uf = UnionFind()
    for row in rows:
        first = row["sources"][0]
        for other in row["sources"][1:]:
            uf.union(first, other)
        uf.find(first)
    for row in rows:
        row["group"] = uf.find(row["sources"][0])
    per_group: dict[str, list[int]] = {}
    for r in rows:
        per_group.setdefault(r["group"], [0, 0])[r["label"]] += 1
    split_of = assign_splits({g: (a, t) for g, (a, t) in per_group.items()}, args.seed)

    rows.sort(key=lambda r: r["file"])
    with (args.out / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["file", "label", "split", "group"])
        for r in rows:
            writer.writerow([r["file"], r["label"], split_of[r["group"]], r["group"]])

    counts = Counter((split_of[r["group"]], r["label"]) for r in rows)
    sizes = Counter(r["group"] for r in rows)
    print(f"{len(rows)} images in {len(sizes)} source groups (largest group: {max(sizes.values())} images)")
    for name, _ in SPLITS:
        print(f"  {name:5s}: {counts[(name, 0)]:5d} authentic, {counts[(name, 1)]:5d} tampered")
    return 0


if __name__ == "__main__":
    sys.exit(main())

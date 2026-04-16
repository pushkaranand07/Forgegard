import shutil, os
from pathlib import Path

BASE = Path("GenImage_download/Dataset")
DEST = Path("data/ai_image_detection")

MAPPINGS = [
    (BASE / "Train"      / "Real", DEST / "train" / "real"),
    (BASE / "Train"      / "Fake", DEST / "train" / "fake"),
    (BASE / "Test" / "Real", DEST / "val"   / "real"),
    (BASE / "Test" / "Fake", DEST / "val"   / "fake"),
]

for src, dst in MAPPINGS:
    if not src.exists():
        print(f"MISSING: {src}")
        continue
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        shutil.copy2(f, dst / f.name)
    print(f"Copied {len(list(dst.iterdir()))} files → {dst}")

print("\nDone. Final structure:")
for p in sorted(DEST.rglob("*")):
    if p.is_dir():
        n = len(list(p.glob("*")))
        print(f"  {p}  ({n} files)")

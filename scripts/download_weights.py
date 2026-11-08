"""
Download the model weights listed in core/model_manifest.json and verify them.

    python scripts/download_weights.py                 # fetch everything, fail on anything missing
    python scripts/download_weights.py --allow-missing # skip entries with no download URL (CI)

Each file is downloaded to ``<name>.part``, checked against the manifest's SHA-256,
and only then renamed into place, so a failed or tampered download never leaves a
file the loader would pick up. Files already present with the right hash are skipped.

A manifest entry with ``"url": null`` has no public source yet. Its URL can be
supplied through an environment variable named after the file, for example
``FORGEGUARD_WEIGHTS_URL_MODEL_C1_PTH`` for ``model_c1.pth``.

Standard library only, so it runs before any dependency is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "core" / "model_manifest.json"
DEFAULT_DEST = Path(os.getenv("FORGEGUARD_WEIGHTS_DIR", ROOT / "weights"))
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def env_var_for(name: str) -> str:
    return "FORGEGUARD_WEIGHTS_URL_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def url_for(name: str, entry: dict) -> str | None:
    return os.getenv(env_var_for(name)) or entry.get("url")


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "forgeguard-weights-downloader"})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out, CHUNK)


def fetch(name: str, entry: dict, dest: Path, allow_missing: bool) -> bool:
    """Make ``dest/name`` present and verified. Returns False on failure."""
    final = dest / name
    expected = entry["sha256"]

    if final.is_file() and sha256_of(final) == expected:
        print(f"ok        {name} (already present)")
        return True

    url = url_for(name, entry)
    if not url:
        message = f"{name}: no download URL (set {env_var_for(name)} or add 'url' to the manifest)"
        if allow_missing:
            print(f"skipped   {message}")
            return True
        print(f"MISSING   {message}", file=sys.stderr)
        return False

    part = dest / f"{name}.part"
    print(f"download  {name} <- {url}")
    try:
        download(url, part)
    except OSError as exc:
        part.unlink(missing_ok=True)
        print(f"FAILED    {name}: {exc}", file=sys.stderr)
        return False

    actual = sha256_of(part)
    if actual != expected:
        part.unlink()
        print(f"MISMATCH  {name}: got {actual[:12]}…, manifest says {expected[:12]}…", file=sys.stderr)
        return False

    os.replace(part, final)
    print(f"ok        {name} (verified)")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--allow-missing", action="store_true",
                        help="skip entries that have no download URL instead of failing")
    args = parser.parse_args(argv)

    models = json.loads(args.manifest.read_text(encoding="utf-8"))["models"]
    args.dest.mkdir(parents=True, exist_ok=True)
    results = [fetch(name, entry, args.dest, args.allow_missing) for name, entry in models.items()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

"""
core/model_registry.py
======================
Weight integrity and load state for the served models.

- ``core/model_manifest.json`` records the expected SHA-256 of every weight
  file ForgeGuard serves (keyed by file name). The loaders call
  ``verify_weights`` before deserialising anything; a mismatch raises
  ``WeightsIntegrityError``.
- Loaders report success or failure with ``record_loaded`` / ``record_failed``
  so the readiness probe can say "unhealthy" when a model failed to load,
  rather than only checking that the file exists.
- ``model_info`` is the version block attached to API responses.

Files whose name is not in the manifest (e.g. test checkpoints) are not
verified. Set FORGEGUARD_VERIFY_WEIGHTS=false to skip verification entirely,
for example while trying out a new checkpoint before updating the manifest.

No torch import here, so the API layer can use it cheaply.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Any

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_manifest.json")


class ModelUnavailableError(RuntimeError):
    """A model cannot be served (bad hash, incompatible or unreadable checkpoint)."""


class WeightsIntegrityError(ModelUnavailableError):
    """The weight file's SHA-256 does not match core/model_manifest.json."""


class CheckpointMismatchError(ModelUnavailableError):
    """The checkpoint does not fit the model architecture (strict load failed)."""


_lock = threading.Lock()
_hash_cache: dict[str, tuple[int, int, str]] = {}  # abs path -> (size, mtime_ns, sha256)
_state: dict[str, dict[str, Any]] = {}  # abs path -> {"state": "loaded"|"failed", "error": str}
_manifest: dict[str, Any] | None = None


def manifest() -> dict[str, Any]:
    global _manifest
    if _manifest is None:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            _manifest = json.load(f)
    return _manifest


def pipeline_version() -> str:
    return manifest()["pipeline_version"]


def manifest_entry(path: str) -> dict[str, Any] | None:
    return manifest()["models"].get(os.path.basename(path))


def is_validated(path: str) -> bool:
    """True only when the manifest marks this model as having passed a committed evaluation.

    An unvalidated image model still runs, but the API reports its score as
    experimental (label UNVALIDATED) instead of an AUTHENTIC/TAMPERED verdict.
    """
    entry = manifest_entry(path)
    return bool(entry and entry.get("validated") is True)


def verification_enabled() -> bool:
    return os.getenv("FORGEGUARD_VERIFY_WEIGHTS", "true").strip().lower() not in {"0", "false", "no", "off"}


def sha256_of(path: str) -> str:
    """SHA-256 of a file, cached until its size or mtime changes."""
    path = os.path.abspath(path)
    st = os.stat(path)
    with _lock:
        cached = _hash_cache.get(path)
        if cached and cached[0] == st.st_size and cached[1] == st.st_mtime_ns:
            return cached[2]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _lock:
        _hash_cache[path] = (st.st_size, st.st_mtime_ns, digest)
    return digest


def verify_weights(path: str) -> None:
    """Raise WeightsIntegrityError if ``path`` is in the manifest with a different hash."""
    entry = manifest_entry(path)
    if entry is None or not verification_enabled():
        return
    actual = sha256_of(path)
    if actual != entry["sha256"]:
        raise WeightsIntegrityError(
            f"{os.path.basename(path)}: SHA-256 {actual[:12]}… does not match the manifest "
            f"({entry['sha256'][:12]}…)."
        )


def record_loaded(path: str) -> None:
    with _lock:
        _state[os.path.abspath(path)] = {"state": "loaded", "error": None}


def record_failed(path: str, error: BaseException) -> None:
    with _lock:
        _state[os.path.abspath(path)] = {"state": "failed", "error": f"{type(error).__name__}: {error}"}


def load_state(path: str) -> dict[str, Any]:
    """{"state": "loaded"|"failed"|"not_loaded", "error": str|None}"""
    with _lock:
        return dict(_state.get(os.path.abspath(path), {"state": "not_loaded", "error": None}))


def reset_state() -> None:
    """Forget recorded load results (used when caches are invalidated, and by tests)."""
    with _lock:
        _state.clear()


def model_info(path: str) -> dict[str, Any]:
    """Version block for API responses: name, short hash and pipeline version."""
    entry = manifest_entry(path) or {}
    try:
        digest = sha256_of(path)[:12]
    except OSError:
        digest = None
    return {
        "model_name": entry.get("name", os.path.basename(path)),
        "weights_sha256": digest,
        "pipeline_version": pipeline_version(),
    }

"""scripts/download_weights.py: verified downloads driven by core/model_manifest.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import download_weights as dw


def _manifest(tmp_path: Path, entries: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"pipeline_version": "test", "models": entries}), encoding="utf-8")
    return path


def _source(tmp_path: Path, name: str, data: bytes) -> tuple[str, str]:
    src = tmp_path / "remote" / name
    src.parent.mkdir(exist_ok=True)
    src.write_bytes(data)
    return src.as_uri(), hashlib.sha256(data).hexdigest()


def test_downloads_and_verifies(tmp_path):
    url, digest = _source(tmp_path, "a.pth", b"weights-a")
    manifest = _manifest(tmp_path, {"a.pth": {"sha256": digest, "url": url}})
    dest = tmp_path / "weights"

    assert dw.main(["--manifest", str(manifest), "--dest", str(dest)]) == 0
    assert (dest / "a.pth").read_bytes() == b"weights-a"
    assert not list(dest.glob("*.part"))


def test_hash_mismatch_fails_and_leaves_nothing(tmp_path):
    url, _ = _source(tmp_path, "a.pth", b"tampered")
    manifest = _manifest(tmp_path, {"a.pth": {"sha256": "0" * 64, "url": url}})
    dest = tmp_path / "weights"

    assert dw.main(["--manifest", str(manifest), "--dest", str(dest)]) == 1
    assert list(dest.iterdir()) == []


def test_valid_existing_file_is_not_downloaded_again(tmp_path):
    data = b"already here"
    digest = hashlib.sha256(data).hexdigest()
    dest = tmp_path / "weights"
    dest.mkdir()
    (dest / "a.pth").write_bytes(data)
    manifest = _manifest(tmp_path, {"a.pth": {"sha256": digest, "url": "file:///does/not/exist"}})

    assert dw.main(["--manifest", str(manifest), "--dest", str(dest)]) == 0


def test_corrupt_existing_file_is_replaced(tmp_path):
    url, digest = _source(tmp_path, "a.pth", b"good")
    dest = tmp_path / "weights"
    dest.mkdir()
    (dest / "a.pth").write_bytes(b"corrupt")
    manifest = _manifest(tmp_path, {"a.pth": {"sha256": digest, "url": url}})

    assert dw.main(["--manifest", str(manifest), "--dest", str(dest)]) == 0
    assert (dest / "a.pth").read_bytes() == b"good"


def test_entry_without_url_fails_unless_allowed(tmp_path, capsys):
    manifest = _manifest(tmp_path, {"private.pth": {"sha256": "1" * 64, "url": None}})
    dest = tmp_path / "weights"

    assert dw.main(["--manifest", str(manifest), "--dest", str(dest)]) == 1
    assert "no download URL" in capsys.readouterr().err
    assert dw.main(["--manifest", str(manifest), "--dest", str(dest), "--allow-missing"]) == 0


def test_url_can_come_from_environment(tmp_path, monkeypatch):
    url, digest = _source(tmp_path, "private.pth", b"private weights")
    manifest = _manifest(tmp_path, {"private.pth": {"sha256": digest, "url": None}})
    monkeypatch.setenv("FORGEGUARD_WEIGHTS_URL_PRIVATE_PTH", url)

    assert dw.main(["--manifest", str(manifest), "--dest", str(tmp_path / "weights")]) == 0


@pytest.mark.parametrize("name", ["model_c1.pth", "deepfake_detector_b7.pth"])
def test_real_manifest_entries_are_well_formed(name):
    entry = json.loads(Path(dw.DEFAULT_MANIFEST).read_text(encoding="utf-8"))["models"][name]
    assert len(entry["sha256"]) == 64
    assert "url" in entry


def test_video_weights_come_from_upstream_release():
    entry = json.loads(Path(dw.DEFAULT_MANIFEST).read_text(encoding="utf-8"))["models"]["deepfake_detector_b7.pth"]
    assert entry["url"].startswith("https://github.com/selimsef/dfdc_deepfake_challenge/releases/download/0.0.1/")

"""Content-Security-Policy on the single-page app (remediation phase 1.5)."""

from __future__ import annotations

import base64
import hashlib

import pytest

from api import views

pytestmark = pytest.mark.django_db

INLINE = 'try { document.documentElement.dataset.theme = "dark"; } catch (e) {}'


def _sha(script: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"


@pytest.fixture
def spa_index(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text(
        "<!doctype html><html><head>"
        f"<script>{INLINE}</script>"
        '<script type="module" src="/static/app/assets/app.js"></script>'
        "</head><body><div id=root></div></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(views, "SPA_INDEX", str(index))
    views._spa_cache.clear()
    return index


def _policy(response) -> dict:
    header = response["Content-Security-Policy"]
    return {part.split()[0]: part.split()[1:] for part in header.split(";") if part.strip()}


def test_spa_sends_a_strict_policy(client, spa_index):
    policy = _policy(client.get("/analyze"))
    assert policy["default-src"] == ["'self'"]
    assert policy["object-src"] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["base-uri"] == ["'self'"]
    sources = [src for values in policy.values() for src in values]
    assert "'unsafe-inline'" not in sources
    assert "'unsafe-eval'" not in sources


def test_inline_scripts_are_allowed_by_exact_hash(client, spa_index):
    policy = _policy(client.get("/"))
    assert policy["script-src"] == ["'self'", _sha(INLINE)]


def test_edited_inline_script_gets_a_new_hash(client, spa_index):
    first = _policy(client.get("/"))["script-src"]
    spa_index.write_text(spa_index.read_text(encoding="utf-8").replace("dark", "light"), encoding="utf-8")
    second = _policy(client.get("/"))["script-src"]
    assert first != second
    assert _sha(INLINE.replace("dark", "light")) in second


def test_media_previews_and_data_icons_are_allowed(client, spa_index):
    policy = _policy(client.get("/"))
    assert {"'self'", "data:", "blob:"} <= set(policy["img-src"])
    assert {"'self'", "blob:"} <= set(policy["media-src"])


def test_api_responses_are_not_given_the_spa_policy(client):
    assert "Content-Security-Policy" not in client.get("/api/health/live")


def test_real_index_inline_scripts_hash_as_served():
    """The committed web/index.html inline script must hash the same way the view does."""
    from pathlib import Path

    source = (Path(views.settings.BASE_DIR) / "web" / "index.html").read_text(encoding="utf-8")
    hashes = views._inline_script_hashes(source)
    assert len(hashes) == 1 and hashes[0].startswith("'sha256-")

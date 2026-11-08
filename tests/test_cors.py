"""CORS for the API (audit I14: the Vercel frontend could not reach a separate backend;
the preflight got 405 and responses had no CORS headers)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client

FRONTEND = "https://forgeguard.vercel.app"
OTHER = "https://evil.example"
ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.django_db


def preflight(client: Client, path: str, origin: str):
    return client.options(
        path,
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="accept",
    )


class TestAllowedOrigin:
    @pytest.fixture(autouse=True)
    def _allow_frontend(self, settings):
        settings.CORS_ALLOWED_ORIGINS = [FRONTEND]

    def test_preflight_for_an_upload_endpoint_is_allowed(self):
        r = preflight(Client(), "/api/detect-image/", FRONTEND)
        assert r.status_code == 204  # audit: 405
        assert r["Access-Control-Allow-Origin"] == FRONTEND
        assert "POST" in r["Access-Control-Allow-Methods"]
        assert "Accept" in r["Access-Control-Allow-Headers"]
        assert "Access-Control-Allow-Credentials" not in r

    def test_responses_carry_the_origin_and_expose_request_id(self):
        r = Client().get("/api/health/live", HTTP_ORIGIN=FRONTEND)
        assert r.status_code == 200
        assert r["Access-Control-Allow-Origin"] == FRONTEND
        assert "X-Request-ID" in r["Access-Control-Expose-Headers"]
        assert "Retry-After" in r["Access-Control-Expose-Headers"]
        assert "Origin" in r["Vary"]

    def test_error_responses_are_readable_by_the_frontend(self):
        r = Client().post("/api/detect-image/", {}, HTTP_ORIGIN=FRONTEND)
        assert r.status_code == 400
        assert r["Access-Control-Allow-Origin"] == FRONTEND
        assert r.json()["code"] == "INVALID_INPUT"

    def test_other_origins_get_no_cors_headers(self):
        assert "Access-Control-Allow-Origin" not in preflight(Client(), "/api/detect-image/", OTHER)
        r = Client().get("/api/health/live", HTTP_ORIGIN=OTHER)
        assert "Access-Control-Allow-Origin" not in r
        assert "Origin" in r["Vary"]  # caches must not serve one origin's response to another

    def test_pages_outside_the_api_are_untouched(self):
        r = Client().get("/", HTTP_ORIGIN=FRONTEND)
        assert "Access-Control-Allow-Origin" not in r


def test_without_configuration_nothing_changes():
    r = Client().get("/api/health/live", HTTP_ORIGIN=FRONTEND)
    assert "Access-Control-Allow-Origin" not in r
    assert "Origin" not in r.get("Vary", "")


@pytest.mark.parametrize(
    "value",
    ["*", "https://forgeguard.vercel.app/", "forgeguard.vercel.app", "https://a.example/path", "https://*.vercel.app"],
)
def test_settings_reject_anything_but_exact_origins(value):
    env = {**os.environ, "DJANGO_CORS_ALLOWED_ORIGINS": value, "DJANGO_SETTINGS_MODULE": "config.settings"}
    r = subprocess.run([sys.executable, "-c", "import config.settings"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "must be an exact origin" in r.stderr


def test_settings_accept_a_list_of_exact_origins():
    env = {**os.environ, "DJANGO_CORS_ALLOWED_ORIGINS": f"{FRONTEND},http://localhost:5173",
           "DJANGO_SETTINGS_MODULE": "config.settings"}
    r = subprocess.run([sys.executable, "-c", "import config.settings as s; print(s.CORS_ALLOWED_ORIGINS)"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "localhost:5173" in r.stdout

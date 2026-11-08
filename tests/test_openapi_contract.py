"""Real responses match api/openapi.yaml, and every API route is documented.

The schema is strict (additionalProperties: false), so a field added or removed on
either side fails here. The web UI's types are generated from the same file.
Models are stubbed at the lowest level (the score / the network), so the real
request handling, verdict policy and serialisation all run.
"""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
import yaml
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import get_resolver
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from torch import nn

from api import jobs
from core.pipeline import image_processor as ip
from core.pipeline import video_processor as vp
from tests.conftest import make_image

SPEC_PATH = Path(__file__).resolve().parent.parent / "api" / "openapi.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
URI = "urn:forgeguard:openapi"
REGISTRY = Registry().with_resource(URI, Resource.from_contents(SPEC, default_specification=DRAFT202012))

pytestmark = pytest.mark.django_db


def _template_for(url: str) -> str:
    for template in SPEC["paths"]:
        pattern = "^" + re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(template)) + "$"
        if re.match(pattern, url):
            return template
    raise AssertionError(f"{url} is not in api/openapi.yaml")


def check(response, url: str, method: str) -> dict:
    """Validate a response against the spec for its path, method and status; return the body."""
    template = _template_for(url.split("?")[0])
    operation = SPEC["paths"][template][method.lower()]
    status = str(response.status_code)
    assert status in operation["responses"], f"{method} {template} returned undocumented {status}"
    pointer = f"/paths/{template.replace('~', '~0').replace('/', '~1')}/{method.lower()}/responses/{status}"
    declared = operation["responses"][status]
    if "$ref" in declared:
        pointer = declared["$ref"].lstrip("#")
    schema = {"$ref": f"{URI}#{pointer}/content/application~1json/schema"}
    body = response.json()
    errors = sorted(Draft202012Validator(schema, registry=REGISTRY).iter_errors(body), key=str)
    assert not errors, f"{method} {url} {status}: " + "; ".join(
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors[:5])
    return body


# ── Fixtures: models stubbed at the lowest level ─────────────────────────────

class _Faces:
    def extract_face(self, frame):
        return frame[:32, :32]


class _NoFaces:
    def extract_face(self, frame):
        return None


class _ConfidentlyFake(nn.Module):
    def forward(self, x):
        return torch.full((x.shape[0], 1), 3.0)


@pytest.fixture
def models(monkeypatch, fake_weights):
    monkeypatch.setattr(ip, "tampering_score", lambda *a, **k: 0.87)
    monkeypatch.setattr(vp, "get_face_extractor", lambda device: _Faces())
    monkeypatch.setattr(vp, "load_model", lambda *a, **k: _ConfidentlyFake())


def video(tmp_path, name="clip.avi", frames=12) -> SimpleUploadedFile:
    path = tmp_path / name
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 15, np.uint8))
    writer.release()
    return SimpleUploadedFile(name, path.read_bytes())


# ── The spec documents exactly the routes that exist ─────────────────────────

def _django_api_routes() -> set[str]:
    out = set()

    def walk(patterns, prefix=""):
        for p in patterns:
            route = prefix + str(p.pattern)
            if hasattr(p, "url_patterns"):  # include()
                walk(p.url_patterns, route)
            elif route.startswith("api/"):
                out.add("/" + re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", route))

    walk(get_resolver().url_patterns)
    return out


def test_every_api_route_is_documented_and_nothing_else():
    assert _django_api_routes() == set(SPEC["paths"])


def test_the_spec_is_valid_openapi_3_1():
    assert SPEC["openapi"].startswith("3.1")
    Draft202012Validator.check_schema({"$defs": SPEC["components"]["schemas"]})


# ── Successful responses ─────────────────────────────────────────────────────

def test_image_results(client, models):
    body = check(client.post("/api/detect-image/", {"image": make_image()}), "/api/detect-image/", "POST")
    assert body["label"] == "UNVALIDATED"
    body = check(client.post("/api/detect-image/", {"image": make_image("a.png", fmt="PNG")}),
                 "/api/detect-image/", "POST")
    assert body["label"] == "UNSUPPORTED"


def test_video_results(client, models, monkeypatch, tmp_path):
    assert check(client.post("/api/detect-video/", {"video": video(tmp_path)}),
                 "/api/detect-video/", "POST")["label"] == "FAKE"
    monkeypatch.setattr(vp, "get_face_extractor", lambda device: _NoFaces())
    body = check(client.post("/api/detect-video/", {"video": video(tmp_path)}), "/api/detect-video/", "POST")
    assert body["label"] == "UNSURE" and "NO_FACE_DETECTED" in body["notes"]


def test_unified_results(client, models, tmp_path):
    image = check(client.post("/api/detect/", {"file": make_image()}), "/api/detect/", "POST")
    assert image["media_type"] == "image"
    clip = check(client.post("/api/detect/", {"file": video(tmp_path)}), "/api/detect/", "POST")
    assert clip["media_type"] == "video"


def test_batches(client, models, tmp_path):
    files = [make_image(), video(tmp_path), SimpleUploadedFile("notes.txt", b"hi")]
    body = check(client.post("/api/detect/batch", {"file": files}), "/api/detect/batch", "POST")
    assert body["status"] == "partial_error" and body["num_errors"] == 1

    created = check(client.post("/api/batches/", {"file": [make_image(), SimpleUploadedFile("x.txt", b"hi")]}),
                    "/api/batches/", "POST")
    assert created["rejected"][0]["code"] == "INVALID_INPUT"
    check(client.get(created["poll"]), created["poll"], "GET")


def test_jobs(client, models, tmp_path):
    created = check(client.post("/api/jobs/", {"file": make_image()}), "/api/jobs/", "POST")
    assert check(client.get(created["poll"]), created["poll"], "GET")["status"] == "done"

    broken = SimpleUploadedFile("broken.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF")
    created = check(client.post("/api/jobs/", {"file": broken}), "/api/jobs/", "POST")
    failed = check(client.get(created["poll"]), created["poll"], "GET")
    assert failed["status"] == "failed" and failed["result"]["code"] == "INVALID_MEDIA"


def test_pending_when_the_job_outlasts_the_wait(client, models, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "wait_for", lambda *a, **k: None)
    pending = check(client.post("/api/detect-video/", {"video": video(tmp_path)}), "/api/detect-video/", "POST")
    assert pending["status"] == "PENDING"
    pending = check(client.post("/api/detect/batch", {"file": [make_image()]}), "/api/detect/batch", "POST")
    assert pending["status"] == "PENDING" and "batch_id" in pending


def test_health(client, models):
    body = check(client.get("/api/health/"), "/api/health/", "GET")
    assert body["worker"]["mode"] == "in-process"
    assert check(client.get("/api/health/live"), "/api/health/live", "GET") == {"status": "ok"}


# ── Errors: every status the spec declares that tests can provoke ────────────

def test_client_errors(client, models, settings, tmp_path):
    check(client.post("/api/detect-image/"), "/api/detect-image/", "POST")  # 400
    check(client.get("/api/detect-image/"), "/api/detect-image/", "POST")  # 405, documented under the route's POST
    check(client.get("/api/jobs/nope/"), "/api/jobs/nope/", "GET")  # 404
    check(client.get("/api/batches/nope/"), "/api/batches/nope/", "GET")  # 404
    gif = SimpleUploadedFile("a.jpg", b"GIF89a" + b"\0" * 64)
    assert check(client.post("/api/detect-image/", {"image": gif}), "/api/detect-image/", "POST")["code"] == \
        "UNSUPPORTED_MEDIA"  # 415
    not_a_video = SimpleUploadedFile("clip.mp4", b"\0" * 2048)
    assert check(client.post("/api/detect-video/", {"video": not_a_video}),
                 "/api/detect-video/", "POST")["code"] == "INVALID_MEDIA"  # 422 (or 400)
    settings.FORGEGUARD_MAX_REQUEST_MB = 0
    assert check(client.post("/api/detect-image/", {"image": make_image()}),
                 "/api/detect-image/", "POST")["code"] == "PAYLOAD_TOO_LARGE"  # 413


def test_rate_limited(client, models, settings):
    settings.FORGEGUARD_RATE_LIMIT_PER_MINUTE = 1
    client.post("/api/detect-image/", {"image": make_image()})
    assert check(client.post("/api/detect-image/", {"image": make_image()}),
                 "/api/detect-image/", "POST")["code"] == "RATE_LIMITED"  # 429


def test_service_unavailable(client, empty_weights, monkeypatch):
    assert check(client.post("/api/detect-image/", {"image": make_image()}),
                 "/api/detect-image/", "POST")["code"] == "MODEL_UNAVAILABLE"  # 503
    monkeypatch.setattr(jobs, "queue_depth", lambda: 10_000)
    assert check(client.post("/api/jobs/", {"file": make_image()}), "/api/jobs/", "POST")["code"] in (
        "BUSY", "MODEL_UNAVAILABLE")

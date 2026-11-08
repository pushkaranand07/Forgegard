"""
jobs_api.py — the job endpoints, and the helpers the synchronous endpoints share
================================================================================
  POST /api/jobs/            file (+ optional kind)  → 202 {"job_id", ...} | 503 BUSY
  GET  /api/jobs/<id>/       → {"status": queued|running|done|failed, "result": ..., ...}
  POST /api/batches/         repeated `file` fields   → 202 {"batch_id", "jobs", "rejected"}
  GET  /api/batches/<id>/    → progress, then the same shape /api/detect/batch returns

Submitting never waits for a model: the upload is spooled and queued, so web
threads stay free and a full queue is refused immediately (audit I6).
"""

from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import jobs
from .common import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    busy_response,
    error_response,
    media_type_for,
    rate_limited,
    validate_upload,
)
from .errors import ErrorCode

ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# Shared by the synchronous compatibility endpoints
# ─────────────────────────────────────────────────────────────────────────────

def _pending(kind: str, ident: str) -> JsonResponse:
    url = reverse(f"api:api_{kind}_status", args=[ident])
    response = JsonResponse(
        {"status": "PENDING", f"{kind}_id": ident, "poll": url,
         "message": "Analysis is still running. Poll the URL for the result."},
        status=202,
    )
    response["Location"] = url
    return response


def submit_and_respond(kind: str, upload) -> JsonResponse:
    """Queue one job; return its result if it finishes within the sync wait, else 202."""
    try:
        job_id = jobs.submit(kind, upload)
    except jobs.QueueFull:
        return busy_response()
    if jobs.wait_for([job_id], settings.FORGEGUARD_SYNC_WAIT_SECONDS):
        record = jobs.get_job(job_id)
        if record is not None:
            return JsonResponse(record["result"], status=record["http_status"])
    return _pending("job", job_id)


def batch_summary(batch: dict[str, Any]) -> dict[str, Any]:
    """The /api/detect/batch response shape, built from a batch's jobs."""
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = list(batch["rejected"])
    done = 0
    for entry in batch["jobs"]:
        record = jobs.get_job(entry["job_id"]) or {}
        status = record.get("status")
        if status not in jobs.TERMINAL:
            continue
        done += 1
        body = dict(record.get("result") or {})
        if status == jobs.DONE and body.get("label") != "ERROR":
            body.update(file_index=entry["file_index"], file_name=entry["file_name"])
            results.append(body)
        else:
            errors.append({
                "file_index": entry["file_index"],
                "file_name": entry["file_name"],
                "error": body.get("error") or "Detection failed",
                "code": body.get("code") or ErrorCode.INTERNAL_ERROR.value,
            })
    results.sort(key=lambda r: r["file_index"])
    errors.sort(key=lambda e: e["file_index"])
    total = len(batch["jobs"])
    if done < total:
        overall = "running"
    elif not results and errors:
        overall = "error"
    elif errors:
        overall = "partial_error"
    else:
        overall = "success"
    return {
        "batch_id": batch["batch_id"],
        "status": overall,
        "done": done,
        "total": total,
        "results": results,
        "errors": errors,
        "num_success": len(results),
        "num_errors": len(errors),
        "processing_time_ms": (time.time() - batch["created_at"]) * 1000,
    }


def submit_batch_files(request) -> tuple[str | None, JsonResponse | None]:
    """Validate a multi-file upload and queue it. Returns (batch_id, None) or (None, error response)."""
    files = request.FILES.getlist("file")
    if not files:
        return None, error_response("No files provided", 400)
    max_files = settings.FORGEGUARD_MAX_BATCH_FILES
    if len(files) > max_files:
        return None, error_response(f"Too many files: at most {max_files} per batch.", 400)

    accepted, rejected = [], []
    for index, upload in enumerate(files):
        invalid = validate_upload(upload, ALL_EXTENSIONS)
        if invalid:
            rejected.append({"file_index": index, "file_name": upload.name, "error": invalid,
                             "code": ErrorCode.INVALID_INPUT.value})
        else:
            accepted.append((index, upload))
    try:
        return jobs.submit_batch(accepted, rejected), None
    except jobs.QueueFull:
        return None, busy_response()


# ─────────────────────────────────────────────────────────────────────────────
# Job endpoints
# ─────────────────────────────────────────────────────────────────────────────

def _job_view(record: dict[str, Any]) -> dict[str, Any]:
    view = {k: record[k] for k in ("job_id", "kind", "status", "file_name", "created_at", "started_at",
                                   "finished_at", "http_status", "result")}
    if record.get("batch_id"):
        view["batch_id"] = record["batch_id"]
    return view


@csrf_exempt
@require_POST
@rate_limited
def api_jobs_create(request):
    upload = request.FILES.get("file")
    if upload is None:
        return error_response('No file provided. Use field name "file".', 400)
    invalid = validate_upload(upload, ALL_EXTENSIONS)
    if invalid:
        return error_response(invalid, 400)

    kind = request.POST.get("kind") or media_type_for(upload.name)
    if kind not in jobs.KINDS:
        return error_response(f"kind must be one of {', '.join(jobs.KINDS)}.", 400)
    if kind in ("image", "video") and media_type_for(upload.name) != kind:
        return error_response(f"A .{upload.name.rsplit('.', 1)[-1]} file cannot be analysed as {kind}.", 400)

    try:
        job_id = jobs.submit(kind, upload)
    except jobs.QueueFull:
        return busy_response()
    url = reverse("api:api_job_status", args=[job_id])
    response = JsonResponse({"job_id": job_id, "status": jobs.QUEUED, "kind": kind, "poll": url}, status=202)
    response["Location"] = url
    return response


@require_GET
def api_job_status(request, job_id: str):
    record = jobs.get_job(job_id)
    if record is None:
        return error_response("Job not found or expired.", 404, "NOT_FOUND")
    return JsonResponse(_job_view(record))


@csrf_exempt
@require_POST
@rate_limited
def api_batches_create(request):
    batch_id, failure = submit_batch_files(request)
    if failure is not None:
        return failure
    batch = jobs.get_batch(batch_id)
    url = reverse("api:api_batch_status", args=[batch_id])
    response = JsonResponse({"batch_id": batch_id, "jobs": batch["jobs"], "rejected": batch["rejected"],
                             "poll": url}, status=202)
    response["Location"] = url
    return response


@require_GET
def api_batch_status(request, batch_id: str):
    batch = jobs.get_batch(batch_id)
    if batch is None:
        return error_response("Batch not found or expired.", 404, "NOT_FOUND")
    return JsonResponse(batch_summary(batch))

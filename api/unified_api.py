"""
unified_api.py — POST /api/detect/ and POST /api/detect/batch
=============================================================
Synchronous compatibility endpoints over the job queue (api/jobs.py).

/api/detect/        `file` → routed to the image or video model by extension.
                    Waits up to FORGEGUARD_SYNC_WAIT_SECONDS for the result,
                    otherwise 202 with a job id (poll /api/jobs/<id>/).
/api/detect/batch   repeated `file` fields (up to FORGEGUARD_MAX_BATCH_FILES),
                    one job per file. Returns the full results if every file
                    finishes within the wait, otherwise 202 with a batch id
                    (poll /api/batches/<id>/). Large video batches no longer
                    run inside one request, so they cannot hit the worker
                    timeout (audit I11).

Result shapes are unchanged: see docs/api_reference.md.
"""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import jobs
from .common import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, error_response, rate_limited, validate_upload
from .jobs_api import _pending, batch_summary, submit_and_respond, submit_batch_files

ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


@csrf_exempt
@require_POST
@rate_limited
def api_detect(request) -> JsonResponse:
    file_obj = request.FILES.get("file") or request.FILES.get("media") or request.FILES.get("upload_file")
    if file_obj is None:
        return error_response('No file provided. Use field name: "file"', 400)

    invalid = validate_upload(file_obj, ALLOWED_EXTENSIONS)
    if invalid:
        return error_response(invalid, 400)

    return submit_and_respond("unified", file_obj)


@csrf_exempt
@require_POST
@rate_limited
def api_detect_multi(request) -> JsonResponse:
    batch_id, failure = submit_batch_files(request)
    if failure is not None:
        return failure

    batch = jobs.get_batch(batch_id)
    job_ids = [entry["job_id"] for entry in batch["jobs"]]
    if not jobs.wait_for(job_ids, settings.FORGEGUARD_SYNC_WAIT_SECONDS):
        return _pending("batch", batch_id)

    summary = batch_summary(batch)
    return JsonResponse(summary, status=200 if summary["status"] != "error" else 400)

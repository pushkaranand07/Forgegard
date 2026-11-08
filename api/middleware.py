"""
middleware.py — Request context for every request
=================================================
- Tags each request with an ID (honouring a sane incoming X-Request-ID),
  echoes it in the response and stamps it onto every log line.
- Rejects API requests whose declared body exceeds FORGEGUARD_MAX_REQUEST_MB
  before Django starts reading the upload.
- Turns unhandled exceptions in /api/ views into a JSON 500 that carries the
  request ID instead of an HTML error page or a stack trace.
- Writes one access-log line per API request.
"""

from __future__ import annotations

import contextvars
import logging
import re
import time
import uuid

from django.conf import settings

from .common import error_response

logger = logging.getLogger("forgeguard.request")

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_INCOMING_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def current_request_id() -> str:
    return _request_id.get()


class RequestIdLogFilter(logging.Filter):
    """Adds `request_id` to log records so formatters can reference it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _INCOMING_ID.match(incoming) else uuid.uuid4().hex[:16]
        token = _request_id.set(request_id)
        request.request_id = request_id
        start = time.perf_counter()
        is_api = request.path.startswith("/api/")
        try:
            response = self._too_large(request) if is_api else None
            if response is None:
                response = self.get_response(request)
            if is_api and response.status_code == 405 and not response.get("Content-Type", "").startswith(
                "application/json"
            ):
                allow = response.get("Allow", "")
                response = error_response(f"Method {request.method} is not allowed here.", 405,
                                          "METHOD_NOT_ALLOWED")
                response["Allow"] = allow
            response["X-Request-ID"] = request_id
            if is_api:
                logger.info(
                    "%s %s %s %.0fms",
                    request.method, request.path, response.status_code,
                    (time.perf_counter() - start) * 1000,
                )
            return response
        finally:
            _request_id.reset(token)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/"):
            return None  # Django's normal 500 handling
        logger.exception("Unhandled error in %s %s", request.method, request.path)
        return error_response(
            "Internal server error. Quote the request ID if you report this.",
            500,
            "error",
            request_id=request.request_id,
        )

    @staticmethod
    def _too_large(request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return error_response("Invalid Content-Length header.", 400, "error")
        limit_mb = settings.FORGEGUARD_MAX_REQUEST_MB
        if length > limit_mb * 1024 * 1024:
            return error_response(f"Request body exceeds the {limit_mb} MB limit.", 413, "TOO_LARGE")
        return None

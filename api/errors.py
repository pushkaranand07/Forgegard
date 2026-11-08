"""
api/errors.py — the error codes every API error body carries
============================================================
Every error body is {"error": <message>, "status": <legacy code>, "code": <ErrorCode>}.

"status" keeps the values the API has always returned (some lower-case, some
endpoint-specific) so existing clients keep working. "code" comes from this one
closed set and means the same thing on every endpoint (audit I17); new clients
should switch on it.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"          # 400: missing file, bad extension, empty/oversized file
    INVALID_MEDIA = "INVALID_MEDIA"          # 400/422: the file could not be decoded or has no frames
    UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA"  # 415: a format ForgeGuard does not decode
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"  # 413
    RATE_LIMITED = "RATE_LIMITED"            # 429
    BUSY = "BUSY"                            # 503: job queue full
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"  # 503: weights missing, failed verification or loading
    NOT_FOUND = "NOT_FOUND"                  # 404
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"  # 405
    INTERNAL_ERROR = "INTERNAL_ERROR"        # 500


_FROM_LEGACY = {
    "INVALID_IMAGE": ErrorCode.INVALID_MEDIA,
    "INVALID_FILE": ErrorCode.INVALID_MEDIA,
    "EMPTY_VIDEO": ErrorCode.INVALID_MEDIA,
    "NO_VISUAL_FRAMES": ErrorCode.INVALID_MEDIA,
    "UNSUPPORTED_MEDIA": ErrorCode.UNSUPPORTED_MEDIA,
    "TOO_LARGE": ErrorCode.PAYLOAD_TOO_LARGE,
    "RATE_LIMITED": ErrorCode.RATE_LIMITED,
    "BUSY": ErrorCode.BUSY,
    "MODEL_UNAVAILABLE": ErrorCode.MODEL_UNAVAILABLE,
    "model_not_found": ErrorCode.MODEL_UNAVAILABLE,
    "NOT_FOUND": ErrorCode.NOT_FOUND,
    "METHOD_NOT_ALLOWED": ErrorCode.METHOD_NOT_ALLOWED,
}

_FROM_HTTP = {
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA,
    422: ErrorCode.INVALID_MEDIA,
    429: ErrorCode.RATE_LIMITED,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    503: ErrorCode.MODEL_UNAVAILABLE,
}


def code_for(legacy_status: str | None, http_status: int) -> ErrorCode:
    """The ErrorCode for an error, from its legacy status string and HTTP status."""
    if legacy_status in _FROM_LEGACY:
        return _FROM_LEGACY[legacy_status]
    if http_status >= 500 and http_status != 503:
        return ErrorCode.INTERNAL_ERROR
    return _FROM_HTTP.get(http_status, ErrorCode.INVALID_INPUT)


def with_code(body: dict, http_status: int) -> dict:
    """Add "code" to an error body that does not have one yet."""
    if http_status >= 400 and "code" not in body:
        body = {**body, "code": code_for(body.get("status"), http_status).value}
    return body

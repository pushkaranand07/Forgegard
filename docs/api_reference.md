# ForgeGuard API Reference

All endpoints speak JSON and accept `multipart/form-data` uploads. The web UI's
**API** page shows the same reference with copy-paste `curl` examples.

Limits are configurable (see `docs/deployment_guide.md`); clients should read
the live values from `GET /api/health/` rather than hard-coding them.

| Media | Extensions |
|---|---|
| Image | jpg, jpeg, png, bmp, tif, tiff, webp (max 50 megapixels) |
| Video | mp4, avi, webm, mov, mkv, flv, 3gp, wmv, gif |

## `POST /api/detect-image/`

Field `image`. Level 1 checks metadata for editing-software signatures; Level 2
runs error-level analysis (ELA) through a CNN.

```json
{
  "label": "TAMPERED",
  "predicted_class": 0,
  "authentic_prob": 0.1584,
  "tampered_prob": 0.8416,
  "confidence_pct": 84.16,
  "device": "cpu",
  "level1": {
    "software_found": true,
    "software_signature": "Adobe Photoshop 25.0 (Windows)",
    "notes": ["Software signature found: Adobe Photoshop 25.0 (Windows)"]
  },
  "original_image": null,
  "processing_time_ms": 461.6
}
```

`predicted_class`: 0 = tampered, 1 = authentic. `original_image` is the saved
filename only when the server runs with `FORGEGUARD_KEEP_UPLOADS=true`.

## `POST /api/detect-video/`

Field `video`. Samples 32 evenly spaced frames, crops the face in each with
MTCNN, and scores each crop with EfficientNet-B7.

```json
{
  "label": "FAKE",
  "predicted_class": 0,
  "fake_prob": 0.987,
  "real_prob": 0.013,
  "confidence_pct": 98.7,
  "device": "cpu",
  "num_frames_processed": 32,
  "frame_predictions": [0.98, 0.97, 0.99],
  "processing_time_ms": 21540.2,
  "notes": [],
  "status": "success"
}
```

`label` is `REAL`, `FAKE`, or `UNSURE` when no face was found in any frame
(then `status` is `NO_FACE_DETECTED`). `frame_predictions` holds one fake
probability per detected face.

## `POST /api/detect/`

Field `file`. Routes to the image or video model by extension and returns a
unified result: `media_type`, `label`, `confidence_pct`, `device`,
`processing_time_ms`, plus `level1`/`level2` for images or
`num_frames_processed`/`frame_predictions`/`notes` for videos. If the file is
accepted but cannot be analysed, the response is 422 (bad media) or 500
(server fault) with `"label": "ERROR"` and the reason in `error`.

## `POST /api/detect/batch`

Repeat the `file` field for each file (up to 20). Files are analysed in order.

```json
{
  "status": "partial_error",
  "results": [{ "...unified result...": "", "file_index": 0, "file_name": "a.jpg" }],
  "errors": [{ "file_index": 1, "file_name": "b.mp4", "error": "Cannot open video file" }],
  "num_success": 1,
  "num_errors": 1,
  "processing_time_ms": 23110.0
}
```

HTTP 200 unless every file failed (then 400).

## `GET /api/health/` and `GET /api/health/live`

`/api/health/live` always returns `{"status": "ok"}` while the process is up.
`/api/health/` reports device, model files (`present`, `loaded`, `size_mb`)
and the active limits; it returns 503 with `"status": "degraded"` when a
weight file is missing.

## Errors

Every error body is `{"error": "<human-readable message>", "status": "<CODE>"}`,
and every response carries an `X-Request-ID` header to quote in bug reports.

| HTTP | `status` | When |
|---|---|---|
| 400 | `error` | No file, unsupported extension, empty or oversized file, too many batch files |
| 400 | `INVALID_IMAGE` | Not a decodable image, truncated, or over 50 megapixels |
| 400 | `INVALID_FILE`, `EMPTY_VIDEO`, `NO_VISUAL_FRAMES` | Video cannot be opened or has no frames |
| 404 | `NOT_FOUND` | Unknown `/api/` path |
| 405 | — | Wrong HTTP method |
| 413 | `TOO_LARGE` | Request body over `FORGEGUARD_MAX_REQUEST_MB` |
| 422 | `error` | `/api/detect/` only: accepted but could not be analysed |
| 429 | `RATE_LIMITED` | Per-IP limit reached; see `Retry-After` |
| 500 | `error` | Unexpected server failure (details are logged, never returned) |
| 503 | `model_not_found` | Weights missing on the server |
| 503 | `BUSY` | All inference slots busy for too long; see `Retry-After` |

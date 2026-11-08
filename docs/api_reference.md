# ForgeGuard API Reference

All endpoints speak JSON and accept `multipart/form-data` uploads. The web UI's
**API** page shows the same reference with copy-paste `curl` examples.

Limits are configurable (see `docs/deployment_guide.md`); clients should read
the live values from `GET /api/health/` rather than hard-coding them.

**Analysis runs as a background job.** The four `detect` endpoints keep the
response shapes below: they wait up to `FORGEGUARD_SYNC_WAIT_SECONDS` (default
20 s) for the job, which covers images. If the job takes longer (usually video,
or a large batch) they return **`202 Accepted`** instead:

```json
{ "status": "PENDING", "job_id": "4f1c…", "poll": "/api/jobs/4f1c…/", "message": "…" }
```

(`batch_id` and `/api/batches/<id>/` for batches; the URL is also in the
`Location` header.) Poll it as described under [Jobs](#jobs-and-batches).

| Media | Extensions |
|---|---|
| Image | jpg, jpeg, png, webp (max 50 megapixels). The real format is read from the file and must match the extension; anything else gets `415 UNSUPPORTED_MEDIA` |
| Video | mp4, avi, webm, mov, mkv, flv, 3gp, wmv, gif |

## `POST /api/detect-image/`

Field `image`. Level 1 checks metadata for editing-software signatures; Level 2
runs error-level analysis (ELA) through a CNN.

```json
{
  "label": "UNVALIDATED",
  "predicted_class": -1,
  "authentic_prob": 0.1584,
  "tampered_prob": 0.8416,
  "confidence_pct": null,
  "experimental": true,
  "reason": "This model has not passed a committed evaluation, so no verdict is given. The score is experimental and uncalibrated.",
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

`label` never claims more than the model's evaluation supports (audit I1, I2):

| `label` | When | Scores |
|---|---|---|
| `AUTHENTIC` / `TAMPERED` | JPEG, and the model is marked `"validated": true` in `core/model_manifest.json` | probabilities and `confidence_pct`; `predicted_class` 1 / 0 |
| `UNVALIDATED` | JPEG, and the model has not passed a committed evaluation (**the deployed model**) | `authentic_prob` / `tampered_prob` as an experimental, uncalibrated score; `confidence_pct` null; `predicted_class` -1; `experimental: true` |
| `UNSUPPORTED` | PNG or WebP: error level analysis needs JPEG compression | all scores null; the model is not run; `reason` explains |

Level 1 (metadata) is reported for every format. `original_image` is the saved
filename only when the server runs with `FORGEGUARD_KEEP_UPLOADS=true`. On
`/api/detect/`, the same fields appear under `level2`.

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

(Values are illustrative, not measured results.)

`label` is `REAL`, `FAKE`, or `UNSURE` when no face was found in any frame.
In the `UNSURE` case `status` is `NO_FACE_DETECTED` and the three score fields are `null`.
`frame_predictions` holds one fake score per detected face (one face per sampled frame).
The response also carries the `model` version block described below.

## `POST /api/detect/`

Field `file`. Routes to the image or video model by extension and returns a
unified result: `media_type`, `label`, `confidence_pct`, `device`,
`processing_time_ms`, plus `level1`/`level2` for images or
`num_frames_processed`/`frame_predictions`/`notes` for videos. If the file is
accepted but cannot be analysed, the response is 422 (bad media) or 500
(server fault) with `"label": "ERROR"` and the reason in `error`.

## `POST /api/detect/batch`

Repeat the `file` field for each file (up to 20). Each file becomes one job;
images are queued ahead of videos.

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

HTTP 200 unless every file failed (then 400), or 202 with a `batch_id` when
the batch is still running after the wait.

## Jobs and batches

Submit work without waiting, then poll. Submissions are refused at once with
`503 BUSY` (and `Retry-After`) when `FORGEGUARD_MAX_QUEUE` jobs are already
waiting.

### `POST /api/jobs/`

Field `file`; optional `kind` (`image`, `video` or `unified`; default: by
extension). Returns **202**:

```json
{ "job_id": "4f1c…", "status": "queued", "kind": "video", "poll": "/api/jobs/4f1c…/" }
```

### `GET /api/jobs/<id>/`

```json
{
  "job_id": "4f1c…", "kind": "video", "status": "done",
  "file_name": "clip.mp4", "created_at": 1794100000.1, "started_at": 1794100001.0,
  "finished_at": 1794100023.4, "http_status": 200,
  "result": { "...same body /api/detect-video/ returns...": "" }
}
```

`status` is `queued`, `running`, `done` or `failed`. When finished,
`http_status` and `result` are exactly what the synchronous endpoint would have
returned (for `failed`, `result` is the usual error body). Records expire after
`FORGEGUARD_JOB_TTL` (default 1 hour); unknown or expired ids return 404.

### `POST /api/batches/` and `GET /api/batches/<id>/`

Repeat `file` (up to 20). `POST` returns 202 with `batch_id`, the queued `jobs`
and any `rejected` files. `GET` returns the `/api/detect/batch` shape plus
`batch_id`, `done` and `total`; `status` is `running` until every job finished.


## `GET /api/health/` and `GET /api/health/live`

`/api/health/live` always returns `{"status": "ok"}` while the web process is
up; it does no I/O, so it answers under any load.
`/api/health/` reports `pipeline_version`, the worker's device, the active
limits, a `worker` block (`alive`, `queue_reachable`, `queue_depth`,
`last_seen_seconds`) and, per model: `present`, `loaded` (in the worker),
`size_mb`, `weights_sha256` (first 12 hex digits), `verified` (hash matches
`core/model_manifest.json`; `null` if not checked), `load_state` (`loaded` /
`failed` / `not_loaded`), `load_error` and `healthy`. It returns 503 with
`"status": "degraded"` unless a worker reported in the last 30 s and both
models are healthy.

## Model version block

Every successful detection response (and each batch result) includes:

```json
"model": {"model_name": "IMDModel (ELA + CNN)", "weights_sha256": "b6b76a422a82", "pipeline_version": "1.1.0"}
```

## Missing scores

When the model produces no score (no face detected, unreadable input), the
score fields `fake_prob`, `real_prob` and `confidence_pct` are `null` rather
than a placeholder number.

## Errors

Every error body is `{"error": "<human-readable message>", "status": "<CODE>"}`,
and every response carries an `X-Request-ID` header to quote in bug reports.

| HTTP | `status` | When |
|---|---|---|
| 400 | `error` | No file, unsupported extension, empty or oversized file, too many batch files |
| 400 | `INVALID_IMAGE` | Not a decodable image, truncated, or over 50 megapixels |
| 415 | `UNSUPPORTED_MEDIA` | A recognised image format other than JPEG, PNG or WebP, or a format that does not match the extension (e.g. PNG bytes named `.jpg`) |
| 400 | `INVALID_FILE`, `EMPTY_VIDEO`, `NO_VISUAL_FRAMES` | Video cannot be opened or has no frames |
| 404 | `NOT_FOUND` | Unknown `/api/` path, or an unknown/expired job or batch id |
| 405 | — | Wrong HTTP method |
| 413 | `TOO_LARGE` | Request body over `FORGEGUARD_MAX_REQUEST_MB` |
| 422 | `error` | `/api/detect/` only: accepted but could not be analysed |
| 429 | `RATE_LIMITED` | Per-IP limit reached; see `Retry-After` |
| 500 | `error` | Unexpected server failure (details are logged, never returned) |
| 503 | `model_not_found` | Weights missing on the server |
| 503 | `MODEL_UNAVAILABLE` | Weights present but failed the hash check or could not be loaded (see `/api/health/`) |
| 202 | `PENDING` | `detect` endpoints: the job outlasted the wait; poll the `poll` URL |
| 503 | `BUSY` | The job queue is full (`FORGEGUARD_MAX_QUEUE`); refused immediately, see `Retry-After` |

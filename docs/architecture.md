# Architecture

ForgeGuard is a Django web process (gunicorn, `gthread`) that serves a JSON API and a
pre-built React UI, plus a separate **worker** process that runs the models. Web requests
never run a model: they validate the upload, spool it, queue a job and return. The worker
loads both models once and runs jobs one at a time.

```
                 ┌──────────── web (gunicorn, ~75 MB, never imports torch) ────────────┐
client ── POST ─►│ validate upload ─► spool file ─► enqueue job ─► wait ≤ 20 s or 202   │
       ◄─ poll ──│ GET /api/jobs/<id>/  ◄── job record (status, result)                 │
                 └──────────────────────────────┬──────────────────────────────────────┘
                              queue + job records │ (SQLite file, or Redis)
                 ┌──────────── worker (run_worker, ~0.9 GB models) ────────────────────┐
                 │ dequeue (images first) ─► run pipeline ─► store result ─► delete file │
                 │                                                                       │
                 │  Video: 32 frames, streamed ─► MTCNN crop ─► B7 logit ─► aggregate    │
                 │  Image: EXIF Software tag ─► ELA (native res, strips) ─► IMDModel     │
                 │  Heartbeat every 10 s ─► /api/health/ readiness                       │
                 └───────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Location | Notes |
|---|---|---|
| Upload rules, error shape, rate limit | `api/common.py` | Extension and size checks; per-IP limit stored in the Django cache (Redis when configured, so it holds across processes). |
| Job queue and records | `api/jobs.py` | Huey. `submit()` refuses with `QueueFull` (→ 503 BUSY) when `FORGEGUARD_MAX_QUEUE` jobs wait. Job and batch records live in the queue backend's key-value store and expire after `FORGEGUARD_JOB_TTL`. Image jobs have higher priority than video jobs. |
| Analysis runners | `api/analysis.py` | One function per job kind, returning `(http_status, body)`; imports the pipelines lazily so the web process never loads torch. |
| Job API | `api/jobs_api.py` | `/api/jobs/`, `/api/batches/`, and the submit-then-wait helper the synchronous endpoints share. At most `FORGEGUARD_MAX_SYNC_WAITERS` requests wait at once, so web threads stay free. |
| Synchronous endpoints | `api/image_api.py`, `api/video_api.py`, `api/unified_api.py` | Same URLs and response shapes as before; they submit a job and wait up to `FORGEGUARD_SYNC_WAIT_SECONDS`, else 202. |
| Health | `api/health_api.py` | Liveness: no I/O. Readiness: weights present and hash-verified, queue reachable, worker heartbeat younger than 30 s, models loaded in the worker. |
| Worker | `api/management/commands/run_worker.py` | Warms up models (`api/warmup.py`), starts the heartbeat, runs the Huey consumer with thread workers (Huey's process workers are not available on Windows). |
| Image pipeline | `core/pipeline/image_processor.py`, `core/pipeline/safe_image.py` | Only JPEG/PNG/WebP decoders run on uploads; ELA at native resolution in uint8 strips (bit-identical to whole-image ELA). |
| Video pipeline | `core/pipeline/video_processor.py` | Port of the DFDC 1st-place inference path (see [CREDITS.md](../CREDITS.md)). Frames streamed and reduced to face crops; resolution capped at 4096×4096. No face in any frame → `UNSURE`. |
| Model integrity | `core/model_registry.py` | SHA-256 manifest check before deserialising; strict, `weights_only` loading. |

## Deployment shapes

| Shape | Queue | When |
|---|---|---|
| Local / single host | SQLite file in `FORGEGUARD_SPOOL_DIR` | Development (works on Windows), small single-server deployments. One web process. |
| docker-compose | Redis | Production: web, worker and redis containers with separate memory limits; scale with `--scale worker=N`. |

Web and worker must share `FORGEGUARD_SPOOL_DIR` (same host, or a shared volume).

## Design decisions

- **Why a queue, not a semaphore:** a semaphore inside the web server's thread pool can't
  refuse work: excess requests queue in the server before they reach it, and health checks
  wait in the same queue (the audit measured 178 s waits and timed-out probes). Moving work
  to a separate process removes both problems at the root.
- **Why Huey:** one code path with two backends. SQLite needs no extra service and runs on
  Windows; Redis is used in docker-compose. RQ's worker does not run on Windows.
- **Why keep the synchronous endpoints:** existing callers keep working. Images still
  finish inside the wait; only slow work turns into 202.

## Known constraints

- **Throughput:** ~20–25 s per video per worker on CPU, so roughly 2–3 videos per minute
  per worker ([perf.md](perf.md)). Add workers to scale.
- **No hard per-job timeout:** thread workers can't be killed mid-job. Video jobs are
  bounded by design (32 sampled frames, capped resolution), but a pathological input could
  still keep one worker busy.
- **SQLite queue is single-host:** use Redis when web and worker run on different hosts or
  with more than one web process.

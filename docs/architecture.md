# Architecture

ForgeGuard is a single Django process (gunicorn, `gthread` workers) serving a JSON API and a pre-built React UI. Both models are loaded once per worker process and shared across that worker's request threads.

```
client ──► Django view ──► validate upload ──► scratch file ──► inference slot (semaphore)
                                                                     │
                     ┌───────────────────────────────────────────────┴──────────────┐
                     ▼                                                              ▼
        Video: read 32 frames → MTCNN (top face/frame)              Image: EXIF Software tag
               → resize/pad 380 → B7 logit → sigmoid                        → ELA (JPEG q90, ×10)
               → confident_strategy                                         → 128×128 → IMDModel
                     └───────────────────────────────┬──────────────────────────────┘
                                                     ▼
                                       JSON result (scratch file deleted)
```

## Components

| Component | Location | Notes |
|---|---|---|
| Upload rules, error shape, rate limit, concurrency guard | `api/common.py` | Extension and size checks. A `BoundedSemaphore` caps concurrent inferences (default 1); requests wait up to `FORGEGUARD_INFERENCE_QUEUE_TIMEOUT` and then get `503 BUSY`. |
| Endpoints | `api/image_api.py`, `api/video_api.py`, `api/unified_api.py`, `api/health_api.py` | The batch endpoint processes files one after another inside a single request. |
| Request IDs, JSON 404/500 | `api/middleware.py` | |
| Video pipeline | `core/pipeline/video_processor.py` | Port of the DFDC 1st-place inference path (see [CREDITS.md](../CREDITS.md)). Typed exceptions (`InvalidFileException`, `EmptyVideoException`, `NoVisualFramesException`) map to 4xx responses. No face in any frame → `UNSURE`. |
| Image pipeline | `core/pipeline/image_processor.py` | Pixel-count cap before decoding; ELA and CNN. |
| Model caches | both pipeline modules | One instance per (weights, device), created under a lock so concurrent first requests share one load. |
| Warm-up | `api/warmup.py` | Loads both models at startup. |

## Known constraints

- **Throughput:** one inference slot and ~20–25 s per video on CPU (manual measurement) means roughly 2–3 videos per minute per process.
- **Synchronous requests:** video and batch requests run inside the HTTP request. A large batch can exceed the gunicorn timeout (300 s), which kills the worker. Moving video work to background jobs is planned.
- **Rate limiter:** uses `LocMemCache`, which is per process. It's correct only with a single worker.

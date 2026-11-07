# Performance and capacity

Measured with `scripts/loadtest.py` on 2026-11-08. Windows 11, Ryzen 7 4800H (8 cores), CPU only.
Web: waitress with 16 threads (mirrors gunicorn `gthread`, 16 threads). One worker
(`manage.py run_worker`, 1 job at a time). SQLite queue. Video: a 3 s, 720×1280 real
face clip. Image: a 400×300 JPEG.

The "before" column is the November 2026 audit (single process, inference inside the
request, 4 threads).

## Overload: 6 concurrent videos plus 1 image

```
python scripts/loadtest.py --base http://127.0.0.1:8790 --video clip.mp4 --image photo.jpg --videos 6
```

| Measurement | Before (audit) | After |
|---|---|---|
| Image request sent during the burst | 200 after **178.5 s** | 200 after **9.1 s** (waits only for the video already running) |
| Liveness probes (5 s timeout) | **3 / 3 timed out** | **123 / 123 OK**, median 6 ms, max 54 ms |
| Video submissions | Held open until processed (up to 181 s) | 202 + job id after the 20 s sync wait |
| Queued videos | n/a | First done after 30 s, last after 123 s (~20 s each, one worker) |

## Queue full

Second web instance with `FORGEGUARD_MAX_QUEUE=2`, sharing the same worker; 6 videos
submitted back to back:

| | Before (audit) | After |
|---|---|---|
| Responses | Never returned 503; requests waited | 202, 202, then **503 BUSY in ~17 ms** each, with `Retry-After: 30` |

## Memory

| Process | Before | After |
|---|---|---|
| Web process, idle | 1095 MB (held both models) | **73 MB** (never imports torch) |
| Worker, idle with both models | n/a | 908 MB |
| Peak growth, one 49 MP JPEG | +2591 MB | +451 MB (Windows), +477 MB (Linux CI) |
| Peak growth, one 4096×4096 video | +2776 MB | +258 MB (Windows), +204 MB (Linux CI) |

The peak-growth rows are enforced by `tests/test_memory_bounds.py` (budget 600 MB).

## Capacity on this hardware

- Images: about 15 per second per worker once the model is loaded (audit measurement;
  analysis code unchanged).
- Videos: about 20–25 s each per worker on CPU, so roughly 2–3 per minute per worker.
  Add workers (`docker compose up --scale worker=N`) to raise this; each worker holds its
  own ~0.9 GB of models.
- The web tier is no longer the bottleneck: it only spools uploads and queues jobs.

## Reproducing

```bash
uv run python manage.py run_worker                        # terminal 1
uv run python -m waitress --port=8790 --threads=16 config.wsgi:application   # terminal 2
uv run python scripts/loadtest.py --base http://127.0.0.1:8790 --video clip.mp4 --image photo.jpg
```

Set `FORGEGUARD_RATE_LIMIT_PER_MINUTE=0` for the load test, or the per-IP limit (30/min)
answers first.

# ForgeGuard Deployment Guide

ForgeGuard runs as two processes from one image: **web** (gunicorn serving the
Django API and the pre-built React UI, static files via WhiteNoise) and
**worker** (`python manage.py run_worker`, which loads the models and runs
analysis jobs). They share a queue (SQLite file or Redis) and a spool
directory for uploads. See [architecture.md](architecture.md).

## Sizing

Measured on CPU (8-core Ryzen 7 4800H, PyTorch 2.15); see [perf.md](perf.md):

| Process | RAM | Notes |
|---|---|---|
| Web | ~75 MB | Never loads a model; `docker-compose.yml` limits it to 512 MB |
| Worker, both models loaded | ~0.9 GB | ~5–10 s load at startup |
| Worker during a video job | +~0.8 GB | ~20–25 s for 32 faces; compose limits the worker to 2.5 GB |
| Image job | negligible extra | well under 1 s; images are queued ahead of videos |

A GPU cuts video time to a few seconds but needs a CUDA build of PyTorch
(change the `pytorch-cpu` index in `pyproject.toml`) and a CUDA base image.

Model weights (~320 MB) are not in git. Fetch and verify them with
`python scripts/download_weights.py` (it honours `FORGEGUARD_WEIGHTS_DIR`). The
video checkpoint is downloaded from its upstream release; `model_c1.pth` has no
public URL yet, so supply one with `FORGEGUARD_WEIGHTS_URL_MODEL_C1_PTH`.

**Integrity checks.** Each weight file is checked against the SHA-256 in
`core/model_manifest.json` before it is deserialised, and every load uses
`torch.load(weights_only=True)` with strict key matching. A missing, swapped or
incompatible file makes `/api/health/` return 503 (`"verified": false` or
`"load_state": "failed"`), and detection requests return 503 `MODEL_UNAVAILABLE`.

- **Old copy of `model_c1.pth`** (the pickled module, SHA-256 `5839a0d9…`):
  convert it once with `python scripts/convert_imd_to_state_dict.py`. The
  script keeps the original as `model_c1.legacy-pickle.pth`.
- **Trying a different checkpoint:** set `FORGEGUARD_VERIFY_WEIGHTS=false`
  temporarily, or add its hash to the manifest.

## Docker (recommended)

```bash
cp .env.example .env
# edit .env: DJANGO_DEBUG=false, a real DJANGO_SECRET_KEY, your DJANGO_ALLOWED_HOSTS
docker compose up --build -d
curl http://localhost:8000/api/health/
```

This starts three services: `web` (port 8000), `worker` and `redis`. Uploads
pass from web to worker through the shared `spool` volume; both mount
`./weights` read-only. Compose refuses to start without `DJANGO_SECRET_KEY`.
For hosts without volumes, delete the `weights` line in `.dockerignore` and
rebuild so the weights ship inside the image.

Scale analysis with `docker compose up -d --scale worker=2` (each worker holds
its own ~0.9 GB of models). The image runs as a non-root user; `web` has a
`HEALTHCHECK` against `/api/health/live`, `worker` one that checks its
heartbeat (`python manage.py worker_status`). CI builds this stack and runs a
real job through it on every pull request.

## Platform hosting

Any container host with ≥3 GB RAM works (Render, Railway, Fly.io, Google Cloud
Run, Azure Container Apps, a VM). Typical settings behind the platform's HTTPS
router:

```
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_ALLOWED_HOSTS=forgeguard.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://forgeguard.example.com
DJANGO_BEHIND_PROXY=true
DJANGO_HTTPS=true
GUNICORN_FORWARDED_ALLOW_IPS=*
```

Set `GUNICORN_FORWARDED_ALLOW_IPS=*` only when the container is reachable
solely through the platform router.

**Serverless platforms (Vercel, AWS Lambda) are not suitable** for the backend:
PyTorch plus the B7 checkpoint far exceeds their bundle size limits, and a
video analysis outlasts typical function timeouts.

### Frontend on Vercel, backend elsewhere

The UI can be hosted on Vercel while the API runs on a container host. The
browser then calls the backend directly; uploads never pass through Vercel.

1. **Backend:** allow the frontend's origin, and only that origin:

   ```
   DJANGO_CORS_ALLOWED_ORIGINS=https://<your-project>.vercel.app
   ```

   Use exact origins: scheme and host, no path, no trailing slash. Wildcards are
   rejected at startup. Each Vercel preview deployment has its own URL, so
   previews only work if their origin is listed too.
2. **Vercel:** set the build variable `VITE_API_BASE=https://<backend-host>`
   (no trailing slash) and redeploy. Uploads, job polling and health checks all
   use it.

Why not a Vercel rewrite (`/api/*` proxied to the backend)? Vercel documents a
4.5 MB request-body limit for its functions, and does not say whether external
rewrites share it. Video uploads go up to 100 MB, so this project avoids
depending on undocumented behaviour.

## Configuration reference

All settings are environment variables; `.env.example` lists them with
defaults. The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Must be `false` in production; the app refuses to start without a real `DJANGO_SECRET_KEY` then |
| `DJANGO_HTTPS` | `false` | HTTPS redirect, secure cookies, HSTS |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS`, `DJANGO_HSTS_PRELOAD` | `false` | Opt-in HSTS extensions; enable only when every subdomain is HTTPS |
| `DJANGO_BEHIND_PROXY` | `false` | Trust `X-Forwarded-Proto` / `X-Forwarded-For` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | *(empty)* | Exact browser origins allowed to call `/api/` cross-origin (e.g. the Vercel frontend). Empty: same-origin only |
| `FORGEGUARD_MAX_UPLOAD_MB` | `100` | Per-file limit (UI reads it from `/api/health/`) |
| `FORGEGUARD_MAX_BATCH_FILES` | `20` | Files per batch request |
| `FORGEGUARD_MAX_REQUEST_MB` | `500` | Whole request body, rejected with 413 before reading |
| `FORGEGUARD_QUEUE_BACKEND` | `sqlite` | `sqlite` (queue file in the spool dir; one host) or `redis` |
| `FORGEGUARD_REDIS_URL` | `redis://localhost:6379/0` | Queue, job records and rate-limit counters when the backend is `redis` |
| `FORGEGUARD_SPOOL_DIR` | `<tmp>/forgeguard-spool` | Uploads waiting for the worker (+ the SQLite queue). Web and worker must share it |
| `FORGEGUARD_MAX_QUEUE` | `32` | Waiting jobs before submissions get an immediate 503 `BUSY` |
| `FORGEGUARD_JOB_TTL` | `3600` | Seconds a job result (and an unclaimed upload) is kept |
| `FORGEGUARD_SYNC_WAIT_SECONDS` | `20` | How long the `detect` endpoints wait for their job before answering 202 |
| `FORGEGUARD_MAX_SYNC_WAITERS` | `8` | Requests allowed to wait at once; keep below the gunicorn thread count |
| `FORGEGUARD_MAX_CONCURRENT_INFERENCES` | `1` | Jobs each worker runs at once (1 on CPU) |
| `FORGEGUARD_RATE_LIMIT_PER_MINUTE` | `30` | Detection requests per client IP; `0` disables |
| `FORGEGUARD_KEEP_UPLOADS` | `false` | Keep images analysed by `/api/detect-image/` in `uploaded_images/` (on disk only, never served over HTTP) |
| `FORGEGUARD_VERIFY_WEIGHTS` | `true` | Check weight files against `core/model_manifest.json` before loading |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `1` / `16` | Web process only (no models). With the SQLite queue keep one gunicorn worker |
| `GUNICORN_TIMEOUT` | `120` | Requests wait at most `FORGEGUARD_SYNC_WAIT_SECONDS` for a job |

The rate-limit counters live in each worker's memory. With several workers or
replicas, either accept a per-worker limit or configure a shared Django cache
(e.g. Redis) in `config/settings.py`.

## Without Docker (Linux VM)

```bash
uv sync --frozen --no-dev
uv run python scripts/download_weights.py
(cd web && npm ci && npm run build)
uv run python manage.py collectstatic --noinput
uv run python manage.py migrate --noinput
uv run gunicorn config.wsgi:application -c gunicorn.conf.py   # web
uv run python manage.py run_worker                            # worker (separate service)
```

Run it under systemd (or similar) with the environment variables above.

## Reverse proxy (nginx)

Raise the body limit to match `FORGEGUARD_MAX_REQUEST_MB` and the read timeout
to cover CPU video analysis:

```nginx
server {
    listen 443 ssl;
    server_name forgeguard.example.com;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_request_buffering on;
    }
}
```

## Health checks & operations

- `GET /api/health/live` — liveness: 200 whenever the process serves requests.
- `GET /api/health/` — readiness: 200 when both weight files are present and
  verified, the queue is reachable, and a worker reported a heartbeat in the
  last 30 s with its models loaded; 503 (`"status": "degraded"`) otherwise.
  The `worker` block shows `alive`, `queue_depth` and `last_seen_seconds`.
- `python manage.py worker_status` — exit 0 if a worker heartbeat is fresh.
- Every response carries `X-Request-ID` (an incoming one is honoured), and
  every log line includes it, so a user-reported ID finds the exact request.
- Logs go to stdout. `ENABLE_FILE_LOGGING=true` adds a rotating file in `logs/`.

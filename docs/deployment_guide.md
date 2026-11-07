# ForgeGuard Deployment Guide

ForgeGuard ships as a single container: gunicorn serves the Django API and the
pre-built React UI (static files via WhiteNoise). No database, queue or
external service is required.

## Sizing

Measured on CPU (PyTorch 2.11, 32 sampled frames):

| | RAM | Time |
|---|---|---|
| Process with both models loaded | ~0.9 GB | ~5–10 s load (done at startup by warm-up) |
| Peak during one video analysis | ~1.7 GB | ~20–25 s for 32 faces |
| Image analysis | negligible extra | well under 1 s |

Give the container **3 GB of RAM** for the defaults. A GPU cuts video time to a
few seconds but needs a CUDA build of PyTorch (swap the index URL in the
Dockerfile) and a CUDA base image.

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

`docker-compose.yml` mounts `./weights` read-only. For hosts without volumes,
delete the `weights` line in `.dockerignore` and rebuild so the weights ship
inside the image.

The image runs as a non-root user, listens on `$PORT` (default 8000), and has a
Docker `HEALTHCHECK` against `/api/health/live`.

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

**Serverless platforms (Vercel, AWS Lambda) are not suitable**: PyTorch plus
the B7 checkpoint far exceeds their bundle size limits, and a video analysis
outlasts typical function timeouts.

## Configuration reference

All settings are environment variables; `.env.example` lists them with
defaults. The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Must be `false` in production; the app refuses to start without a real `DJANGO_SECRET_KEY` then |
| `DJANGO_HTTPS` | `false` | HTTPS redirect, secure cookies, HSTS |
| `DJANGO_BEHIND_PROXY` | `false` | Trust `X-Forwarded-Proto` / `X-Forwarded-For` |
| `FORGEGUARD_MAX_UPLOAD_MB` | `100` | Per-file limit (UI reads it from `/api/health/`) |
| `FORGEGUARD_MAX_BATCH_FILES` | `20` | Files per batch request |
| `FORGEGUARD_MAX_REQUEST_MB` | `500` | Whole request body, rejected with 413 before reading |
| `FORGEGUARD_MAX_CONCURRENT_INFERENCES` | `1` | Model runs at once per worker; extra requests queue |
| `FORGEGUARD_INFERENCE_QUEUE_TIMEOUT` | `120` | Seconds a queued request waits before a 503 `BUSY` |
| `FORGEGUARD_RATE_LIMIT_PER_MINUTE` | `30` | Detection requests per client IP; `0` disables |
| `FORGEGUARD_KEEP_UPLOADS` | `false` | Keep images analysed by `/api/detect-image/` in `uploaded_images/` (on disk only, never served over HTTP) |
| `FORGEGUARD_WARMUP_MODELS` | `not DEBUG` | Load models when the worker starts |
| `FORGEGUARD_VERIFY_WEIGHTS` | `true` | Check weight files against `core/model_manifest.json` before loading |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `1` / `4` | Each worker loads its own models — scale threads first |
| `GUNICORN_TIMEOUT` | `300` | Long enough for CPU video analysis |

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
uv run gunicorn config.wsgi:application -c gunicorn.conf.py
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
- `GET /api/health/` — readiness: 200 when both weight files are present,
  503 (`"status": "degraded"`) otherwise; `models.*.loaded` turns `true` once
  warm-up has finished.
- Every response carries `X-Request-ID` (an incoming one is honoured), and
  every log line includes it, so a user-reported ID finds the exact request.
- Logs go to stdout. `ENABLE_FILE_LOGGING=true` adds a rotating file in `logs/`.

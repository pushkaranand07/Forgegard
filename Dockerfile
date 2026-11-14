# syntax=docker/dockerfile:1
#
# ForgeGuard production image (CPU inference).
#
#   docker build -t forgeguard .
#   docker run -p 8000:8000 -e DJANGO_SECRET_KEY=... -v "$PWD/weights:/app/weights:ro" forgeguard
#
# Model weights are NOT baked in by default (see .dockerignore). Mount them at
# /app/weights, or delete the `weights/` line in .dockerignore to ship them in
# the image (handy for PaaS hosts without volumes; adds ~320 MB).

# ── Stage 1: build the React UI ─────────────────────────────────────────────
# Base images are pinned by digest; Dependabot bumps them (.github/dependabot.yml).
FROM node:22-alpine@sha256:0e1754758c2df4cfa3e68d59e2e1b7374bb7fd9ea6328eaaacf15cc934af8202 AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# vite.config.ts writes the bundle to ../frontend/static/app
RUN npm run build


# ── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM astral/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    DJANGO_DEBUG=false \
    DJANGO_SQLITE_PATH=/tmp/forgeguard.sqlite3 \
    FORGEGUARD_TMP_DIR=/tmp/forgeguard \
    FORGEGUARD_SPOOL_DIR=/var/forgeguard \
    FORGEGUARD_WEIGHTS_DIR=/app/weights \
    PORT=8000

# OpenCV (headless) still needs glib at runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so code changes do not invalidate this layer. Exact
# versions and hashes come from uv.lock; --frozen fails if the lock is stale.
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY . .
COPY --from=web /src/frontend/static/app ./frontend/static/app

# collectstatic only needs settings to import; this throwaway key never serves traffic
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    # UID 1000: Hugging Face Spaces run containers as user 1000, and the
    # writable directories below must belong to whoever runs the process
    && useradd --create-home --uid 1000 forgeguard \
    && mkdir -p /app/weights /tmp/forgeguard /var/forgeguard \
    && chown -R forgeguard /app/weights /tmp/forgeguard /var/forgeguard

USER forgeguard
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health/live', timeout=4)"

# Default command: the web server. FORGEGUARD_ROLE=worker runs the job worker
# and FORGEGUARD_ROLE=all runs both in one container (docker/entrypoint.sh);
# docker-compose.yml runs the worker as a separate service.
CMD ["bash", "docker/entrypoint.sh"]

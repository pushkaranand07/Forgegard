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
FROM astral/uv:0.8.17@sha256:e4644cb5bd56fdc2c5ea3ee0525d9d21eed1603bccd6a21f887a938be7e85be1 AS uv

FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    DJANGO_DEBUG=false \
    DJANGO_SQLITE_PATH=/tmp/forgeguard.sqlite3 \
    FORGEGUARD_TMP_DIR=/tmp/forgeguard \
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
    && useradd --create-home --uid 10001 forgeguard \
    && mkdir -p /app/weights /tmp/forgeguard \
    && chown -R forgeguard /app/weights /tmp/forgeguard

USER forgeguard
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health/live', timeout=4)"

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application -c gunicorn.conf.py"]

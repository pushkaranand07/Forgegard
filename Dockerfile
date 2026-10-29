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
FROM node:22-alpine AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# vite.config.ts writes the bundle to ../frontend/static/app
RUN npm run build


# ── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
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

# Dependencies first so code changes do not invalidate this layer
# Versions the test suite runs against; bump together
RUN pip install "torch==2.11.0" "torchvision==0.26.0" --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && pip install --no-deps "facenet-pytorch==2.6.0"

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

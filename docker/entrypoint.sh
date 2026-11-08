#!/usr/bin/env bash
# Container entrypoint. FORGEGUARD_ROLE picks what runs:
#   web     (default) the API + UI under gunicorn; never loads a model
#   worker  the job worker that runs the models
#   all     both in one container, for single-container hosts such as a
#           Hugging Face Space (SQLite queue; the container exits if either dies)
# FORGEGUARD_DOWNLOAD_WEIGHTS=true fetches missing weights (hash-checked against
# core/model_manifest.json) before starting, for hosts without a weights volume.
set -euo pipefail

role="${FORGEGUARD_ROLE:-web}"

if [[ "${FORGEGUARD_DOWNLOAD_WEIGHTS:-false}" == "true" ]]; then
  python scripts/download_weights.py --allow-missing
fi

case "$role" in
  web)
    python manage.py migrate --noinput
    exec gunicorn config.wsgi:application -c gunicorn.conf.py
    ;;
  worker)
    exec python manage.py run_worker
    ;;
  all)
    python manage.py migrate --noinput
    python manage.py run_worker &
    worker=$!
    gunicorn config.wsgi:application -c gunicorn.conf.py &
    web=$!
    trap 'kill -TERM "$worker" "$web" 2>/dev/null' TERM INT
    # Exit when either process exits, so the platform restarts the container
    wait -n "$worker" "$web" || true
    kill -TERM "$worker" "$web" 2>/dev/null || true
    wait || true
    exit 1
    ;;
  *)
    echo "Unknown FORGEGUARD_ROLE '$role' (expected web, worker or all)" >&2
    exit 2
    ;;
esac

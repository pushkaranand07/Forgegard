"""
Gunicorn settings for the ForgeGuard web process. Every value can be
overridden with the matching GUNICORN_* environment variable.

The web process never runs a model: it validates uploads, queues jobs and
serves results; the worker (`manage.py run_worker`) runs the models. Threads
are therefore cheap, and plenty of them keep health checks answering while
some requests wait for their job. Keep FORGEGUARD_MAX_SYNC_WAITERS below the
thread count. With the SQLite queue, run one web process per host; with Redis,
any number.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "16"))

# Requests wait at most FORGEGUARD_SYNC_WAIT_SECONDS for a job; this covers slow uploads
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# Recycle workers occasionally to bound memory growth
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "500"))
max_requests_jitter = 50

# The app logs one line per API request itself (with the request ID)
accesslog = None
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Trust X-Forwarded-* from the platform router only when told to
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")

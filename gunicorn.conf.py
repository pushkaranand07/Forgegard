"""
Gunicorn settings for ForgeGuard. Every value can be overridden with the
matching GUNICORN_* environment variable.

Each worker process holds its own copy of both models (~0.9 GB RAM on CPU,
peaking ~1.7 GB during a video analysis), so scale with threads, not workers:
requests share one model instance and FORGEGUARD_MAX_CONCURRENT_INFERENCES
bounds how many run at once.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))

# CPU inference on a long video can take minutes
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
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

"""
Django settings for ForgeGuard.

Every deployment-specific value comes from environment variables (optionally
loaded from a `.env` file in the project root). See `.env.example` for the
full list. Defaults are tuned for local development; `DJANGO_DEBUG=false`
switches on the production hardening below.
"""

import os
import tempfile

from django.core.exceptions import ImproperlyConfigured

# Absolute path to the Django project directory (one level above this file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = BASE_DIR

try:
    from dotenv import load_dotenv

    # Real environment variables always win over the .env file
    load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)
except ImportError:  # python-dotenv is optional
    pass


def env_str(name: str, default: str = '') -> str:
    return os.getenv(name, '').strip() or default


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f'{name} must be an integer, got {raw!r}') from exc


def env_list(name: str, default: str = '') -> list:
    return [item.strip() for item in env_str(name, default).split(',') if item.strip()]


# ─────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────

_INSECURE_DEV_KEY = 'dev-insecure-secret-change-me'

DEBUG = env_bool('DJANGO_DEBUG', True)

SECRET_KEY = env_str('DJANGO_SECRET_KEY', _INSECURE_DEV_KEY)
if not DEBUG and SECRET_KEY in (_INSECURE_DEV_KEY, 'change-me'):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY must be set to a unique, random value when DJANGO_DEBUG=false. '
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(50))"'
    )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')

# Origins allowed to POST forms with a CSRF token, e.g. https://forgeguard.example.com
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Set when a reverse proxy / PaaS router sits in front of the app and sets
# X-Forwarded-Proto and X-Forwarded-For. Never enable it without a proxy:
# clients could then spoof their IP (and dodge the rate limit).
BEHIND_PROXY = env_bool('DJANGO_BEHIND_PROXY', False)
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Set when the site is served over HTTPS: redirects http→https, marks cookies
# secure and sends HSTS.
HTTPS = env_bool('DJANGO_HTTPS', False)
if HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_HSTS_INCLUDE_SUBDOMAINS', False)
    SECURE_HSTS_PRELOAD = env_bool('DJANGO_HSTS_PRELOAD', False)
    # Health checks from the platform usually arrive over plain HTTP
    SECURE_REDIRECT_EXEMPT = [r'^api/health/']

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True


# ─────────────────────────────────────────────
# Application Definition
# ─────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.auth',          # Required by MessageMiddleware and auth context processors
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'api.middleware.RequestContextMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
# ForgeGuard stores no records; the database only backs Django's session and
# messages frameworks (no app code uses them since the legacy UI was removed).

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env_str('DJANGO_SQLITE_PATH', os.path.join(PROJECT_DIR, 'db.sqlite3')),
    }
}

# ─────────────────────────────────────────────
# Background jobs (api/jobs.py)
# ─────────────────────────────────────────────
# Web requests only enqueue; `python manage.py run_worker` runs the models.
# 'sqlite' keeps the queue in a file under FORGEGUARD_SPOOL_DIR (web and worker
# on one host, works on Windows); 'redis' uses FORGEGUARD_REDIS_URL.
FORGEGUARD_QUEUE_BACKEND = env_str('FORGEGUARD_QUEUE_BACKEND', 'sqlite').lower()
if FORGEGUARD_QUEUE_BACKEND not in ('sqlite', 'redis'):
    raise ImproperlyConfigured("FORGEGUARD_QUEUE_BACKEND must be 'sqlite' or 'redis'")
FORGEGUARD_REDIS_URL = env_str('FORGEGUARD_REDIS_URL', 'redis://localhost:6379/0')

# Rate-limit counters: shared through Redis when it is configured, so the limit
# holds across processes and containers; otherwise per process.
if FORGEGUARD_QUEUE_BACKEND == 'redis':
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                          'LOCATION': FORGEGUARD_REDIS_URL, 'KEY_PREFIX': 'fg'}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                          'LOCATION': 'forgeguard'}}


# ─────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'

# IST – Indian Standard Time (UTC+5:30)
TIME_ZONE = env_str('DJANGO_TIME_ZONE', 'Asia/Kolkata')

USE_I18N = False

# USE_TZ = False keeps naive datetime behaviour (no timezone wrapping)
USE_TZ = False


# ─────────────────────────────────────────────
# Static Files (served by WhiteNoise)
# ─────────────────────────────────────────────

# Directory where `collectstatic` gathers files for production deployments
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, 'frontend', 'static'),
]

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # Compression only, no manifest: the React build already fingerprints its
    # files and is served by api.views.spa, which reads index.html directly.
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}


def _is_fingerprinted(path, url):
    """Vite emits content-hashed files under app/assets/ — cache them forever."""
    return url.startswith(STATIC_URL + 'app/assets/')


WHITENOISE_IMMUTABLE_FILE_TEST = _is_fingerprinted


# ─────────────────────────────────────────────
# Uploads & Inference
# ─────────────────────────────────────────────

# Per-file limit enforced by every detection endpoint
FORGEGUARD_MAX_UPLOAD_MB = env_int('FORGEGUARD_MAX_UPLOAD_MB', 100)

# Maximum files accepted by POST /api/detect/batch
FORGEGUARD_MAX_BATCH_FILES = env_int('FORGEGUARD_MAX_BATCH_FILES', 20)

# Whole-request cap, checked against Content-Length before the body is read
FORGEGUARD_MAX_REQUEST_MB = env_int('FORGEGUARD_MAX_REQUEST_MB', 500)

# Jobs a worker process runs at once. A video job adds ~0.8 GB of B7
# activations on top of the ~0.9 GB of loaded models, and on CPU parallel jobs
# only compete for the same cores, so 1 is right unless you have a GPU.
FORGEGUARD_MAX_CONCURRENT_INFERENCES = env_int('FORGEGUARD_MAX_CONCURRENT_INFERENCES', 1)

# Jobs allowed to wait in the queue; beyond this, submissions get 503 BUSY at once
FORGEGUARD_MAX_QUEUE = env_int('FORGEGUARD_MAX_QUEUE', 32)

# Seconds a finished job's result (and an unclaimed upload) is kept
FORGEGUARD_JOB_TTL = env_int('FORGEGUARD_JOB_TTL', 3600)

# The synchronous compatibility endpoints wait this long for their job, then
# return 202 with a job id to poll. At most FORGEGUARD_MAX_SYNC_WAITERS requests
# wait at once so web threads stay free (keep it below the gunicorn thread count).
FORGEGUARD_SYNC_WAIT_SECONDS = env_int('FORGEGUARD_SYNC_WAIT_SECONDS', 20)
FORGEGUARD_MAX_SYNC_WAITERS = env_int('FORGEGUARD_MAX_SYNC_WAITERS', 8)

# Detection requests allowed per client IP per minute (0 disables the limit)
FORGEGUARD_RATE_LIMIT_PER_MINUTE = env_int('FORGEGUARD_RATE_LIMIT_PER_MINUTE', 30)

# Keep a copy of every image analysed by /api/detect-image/ in MEDIA_ROOT (on
# disk only; never served over HTTP). Off by default: uploads are analysed and discarded.
FORGEGUARD_KEEP_UPLOADS = env_bool('FORGEGUARD_KEEP_UPLOADS', False)

# Scratch space for uploads while they are analysed
FORGEGUARD_TMP_DIR = env_str('FORGEGUARD_TMP_DIR', tempfile.gettempdir())

# Uploads waiting for the worker, plus the SQLite queue file. Web and worker
# must see the same directory (a shared volume in docker-compose).
FORGEGUARD_SPOOL_DIR = env_str('FORGEGUARD_SPOOL_DIR', os.path.join(FORGEGUARD_TMP_DIR, 'forgeguard-spool'))

# Directory holding model_c1.pth and deepfake_detector_b7.pth
FORGEGUARD_WEIGHTS_DIR = env_str('FORGEGUARD_WEIGHTS_DIR', os.path.join(BASE_DIR, 'weights'))

# Django buffers uploads above this size to disk instead of memory
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_TEMP_DIR = FORGEGUARD_TMP_DIR
DATA_UPLOAD_MAX_NUMBER_FILES = FORGEGUARD_MAX_BATCH_FILES + 5


# ─────────────────────────────────────────────
# Media Files (uploads kept when FORGEGUARD_KEEP_UPLOADS is on)
# ─────────────────────────────────────────────

MEDIA_URL  = "/media/"
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'uploaded_images')


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

LOG_LEVEL = env_str('DJANGO_LOG_LEVEL', 'INFO').upper()

_handlers = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
        'filters': ['request_id'],
    },
}
_active_handlers = ['console']

# File logging only if explicitly enabled and not on serverless platforms (e.g. Vercel)
_is_serverless = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or os.getenv('K_SERVICE'))
if env_bool('ENABLE_FILE_LOGGING', False) and not _is_serverless:
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        _log_filepath = os.path.join(LOGS_DIR, 'forgeguard.log')
        # Test that file is genuinely writable before registering handler
        with open(_log_filepath, 'a'):
            pass
        _handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _log_filepath,
            'maxBytes': 1024 * 1024 * 50,  # 50 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'filters': ['request_id'],
        }
        _active_handlers.append('file')
    except OSError:
        pass

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {'()': 'api.middleware.RequestIdLogFilter'},
    },
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} [{request_id}] {message}',
            'style': '{',
        },
    },
    'handlers': _handlers,
    'loggers': {
        'django': {
            'handlers': _active_handlers,
            'level': LOG_LEVEL,
        },
        'django.utils.autoreload': {
            'level': 'INFO',
        },
        'forgeguard': {
            'handlers': _active_handlers,
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

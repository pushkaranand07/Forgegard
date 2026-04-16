"""
Django settings for the DeepGuard Deepfake Detection web application.
"""

import os

# Absolute path to the Django project directory (one level above this file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# PROJECT_DIR is the same as BASE_DIR here; kept as a separate name to make
# path construction in views.py more explicit and readable.
PROJECT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '@)0qp0!&-vht7k0wyuihr+nk-b8zrvb5j^1d@vl84cd1%)f=dz'

# SECURITY WARNING: do not run with DEBUG=True in production!
DEBUG = True

# Set to your actual domain or IP in production
ALLOWED_HOSTS = ["*"]


# ─────────────────────────────────────────────
# Application Definition
# ─────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.auth',          # Required by MessageMiddleware and auth context processors
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ml_app.apps.MlAppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project_settings.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(PROJECT_DIR, 'templates')],
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

WSGI_APPLICATION = 'project_settings.wsgi.application'


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(PROJECT_DIR, 'db.sqlite3'),
    }
}


# ─────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'

# IST – Indian Standard Time (UTC+5:30)
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = False

# USE_TZ = False keeps naive datetime behaviour (no timezone wrapping)
USE_TZ = False


# ─────────────────────────────────────────────
# Static Files
# ─────────────────────────────────────────────
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Directory where `collectstatic` gathers files for production deployments
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    # uploaded_images is served as a static directory so the results pages can
    # render frame previews and face-crop thumbnails by filename.
    os.path.join(PROJECT_DIR, 'uploaded_images'),
    os.path.join(PROJECT_DIR, 'static'),
    # NOTE: models/ is intentionally excluded — .pt weight files are large
    # binary assets and must NOT be exposed over HTTP.
]


# ─────────────────────────────────────────────
# Upload Limits
# ─────────────────────────────────────────────

# Only 'video' content-type is accepted on the video upload endpoint
CONTENT_TYPES = ['video']

# Maximum permitted upload size: 100 MB = 100 × 1024 × 1024 bytes
MAX_UPLOAD_SIZE = "104857600"


# ─────────────────────────────────────────────
# Media Files (uploaded videos)
# ─────────────────────────────────────────────

MEDIA_URL  = "/media/"
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'uploaded_videos')


# ─────────────────────────────────────────────
# Logging (production only)
# ─────────────────────────────────────────────

if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': 'deepguard.log',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
            },
        },
    }

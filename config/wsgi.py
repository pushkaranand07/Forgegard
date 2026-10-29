"""
WSGI entry point for ForgeGuard (used by gunicorn: `config.wsgi:application`).

When FORGEGUARD_WARMUP_MODELS is on (the default with DEBUG off), both models
are loaded in a background thread as the worker starts, so the first real
request does not pay the multi-second checkpoint load. /api/health/ reports
`loaded: true` per model once that has finished.
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

from django.conf import settings  # noqa: E402  (needs the app to be set up)

if settings.FORGEGUARD_WARMUP_MODELS:
    from api.warmup import start_warmup  # noqa: E402

    start_warmup()

"""
WSGI entry point for ForgeGuard (used by gunicorn: `config.wsgi:application`).

The web process serves the API and UI only; models are loaded by the worker
(`python manage.py run_worker`, see api/jobs.py).
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

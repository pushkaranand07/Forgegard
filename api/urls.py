"""
urls.py – URL routing for the ml_app (Image & Video detection).

URL routing
───────────
  /api/health/             → JSON API: model / device status (readiness)
  /api/health/live         → JSON API: liveness probe
  /api/detect/             → JSON API: unified forgery detection
  /api/detect/batch        → JSON API: batch detection
  /api/detect-image/       → JSON API: image manipulation detection
  /api/detect-video/       → JSON API: video deepfake detection
  everything else (GET)    → React single-page app (web/)

The legacy template UI (/legacy/, /predict-image/, /predict-video/) was removed:
it bypassed the rate limit and kept every upload (audit I8). Those paths are 404.
"""

from django.urls import path, re_path
from api import views
from api import health_api
from api import video_api
from api import image_api
from api import unified_api


app_name = 'api'

urlpatterns = [
    # API endpoints
    path('api/health/',             health_api.api_health, name='api_health'),
    path('api/health/live',         health_api.api_health_live, name='api_health_live'),
    path('api/detect/',             unified_api.api_detect, name='api_detect'),
    path('api/detect/batch',        unified_api.api_detect_multi, name='api_detect_batch'),
    path('api/detect-image/',       image_api.api_detect_image, name='api_detect_image'),
    path('api/detect-video/',       video_api.api_detect_video, name='api_detect_video'),

    # React app: any other non-API path is a client-side route. Removed legacy
    # paths stay excluded so they 404 instead of returning the app.
    re_path(r'^(?!api/|static/|media/|legacy/|predict-image/|predict-video/).*$', views.spa, name='spa'),
]

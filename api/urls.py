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
  /predict-image/          → legacy image endpoint
  /predict-video/          → legacy video endpoint
  /legacy/...              → original Django-template UI
  everything else          → React single-page app (web/)
"""

from django.urls import path, re_path
from api import views
from api import health_api
from api import video_api
from api import image_api
from api import unified_api


app_name = 'api'

urlpatterns = [
    # Legacy template UI (superseded by the React app)
    path('legacy/',                 views.video_home, name='home'),
    path('legacy/photo/',           image_api.predict_image, name='predict_image'),
    path('legacy/photo-result/',    image_api.predict_image, name='image_result'),
    path('legacy/about/',           views.about, name='about'),

    # API endpoints
    path('api/health/',             health_api.api_health, name='api_health'),
    path('api/health/live',         health_api.api_health_live, name='api_health_live'),
    path('api/detect/',             unified_api.api_detect, name='api_detect'),
    path('api/detect/batch',        unified_api.api_detect_multi, name='api_detect_batch'),
    path('api/detect-image/',       image_api.api_detect_image, name='api_detect_image'),
    path('api/detect-video/',       video_api.api_detect_video, name='api_detect_video'),
    
    # Legacy endpoints (kept for backward compatibility)
    path('predict-image/',          image_api.predict_image, name='legacy_predict_image'),
    path('predict-video/',          video_api.predict_video, name='legacy_predict_video'),

    # React app: any other non-API path is a client-side route
    re_path(r'^(?!api/|static/|media/|legacy/).*$', views.spa, name='spa'),
]

"""
urls.py – URL routing for the ml_app (Image & Video detection).

URL routing
───────────
  /                      → video detection home (upload page)
  /photo/                → image detection (upload page)
  /photo-result/         → image results page  
  /about/                → about page
  /api/detect/           → JSON API: unified forgery detection
  /api/detect/batch      → JSON API: batch detection
  /api/detect-image/     → JSON API: image manipulation detection
  /api/detect-video/     → JSON API: video deepfake detection
  /predict-image/        → legacy image endpoint
  /predict-video/        → legacy video endpoint
"""

from django.urls import path
from api import views
from api import video_api
from api import image_api
from api import unified_api


app_name = 'api'

# Custom 404 handler (must be set at the URL-conf level)
handler404 = views.handler404

urlpatterns = [
    # Video detection home (upload and results on same page)
    path('',                        views.video_home, name='home'),
    
    # Image detection pages
    path('photo/',                  image_api.predict_image, name='predict_image'),
    path('photo-result/',           image_api.predict_image, name='image_result'),
    
    # About page
    path('about/',                  views.about, name='about'),
    
    # API endpoints
    path('api/detect/',             unified_api.api_detect, name='api_detect'),
    path('api/detect/batch',        unified_api.api_detect_multi, name='api_detect_batch'),
    path('api/detect-image/',       image_api.api_detect_image, name='api_detect_image'),
    path('api/detect-video/',       video_api.api_detect_video, name='api_detect_video'),
    
    # Legacy endpoints (kept for backward compatibility)
    path('predict-image/',          image_api.predict_image, name='legacy_predict_image'),
    path('predict-video/',          video_api.predict_video, name='legacy_predict_video'),
]

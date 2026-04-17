"""
urls.py – URL routing for the ml_app (DeepGuard deepfake detection).

URL structure
─────────────
  /                      → index (video upload home page)
  /about/                → about page
  /predict/              → video results page (session-based)
  /api/predict/          → JSON API: video deepfake detection
  /cuda_full/            → error page shown when GPU memory is exhausted
"""

from django.contrib import admin
from django.urls import path, include
from . import views
from . import image_api
from .views import (
    about,
    index,
    predict_page,
    cuda_full,
    api_predict,
)

app_name = 'ml_app'

# Custom 404 handler (must be set at the URL-conf level)
handler404 = views.handler404

urlpatterns = [
    path('',                   index,               name='home'),
    path('about/',             about,               name='about'),
    path('predict/',           predict_page,        name='predict'),
    path('api/predict/',       api_predict,         name='api_predict'),
    path('api/detect-image/',  image_api.api_detect_image, name='api_detect_image'),
    path('predict-image/',     image_api.predict_image, name='predict_image'),
    path('cuda_full/',         cuda_full,           name='cuda_full'),
]

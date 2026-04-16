"""
urls.py – URL routing for the ml_app (DeepGuard deepfake detection).

URL structure
─────────────
  /                      → index (video upload home page)
  /about/                → about page
  /predict/              → video results page (session-based)
  /predict-image/        → photo upload + results page
  /api/predict/          → JSON API: video deepfake detection
  /api/predict-image/    → JSON API: photo deepfake detection
  /cuda_full/            → error page shown when GPU memory is exhausted
"""

from django.contrib import admin
from django.urls import path, include
from . import views
from .views import (
    about,
    index,
    predict_page,
    cuda_full,
    api_predict,
    predict_image_page,
    api_predict_image,
    api_calibrate_image_threshold,
    api_image_calibration_status,
)

app_name = 'ml_app'

# Custom 404 handler (must be set at the URL-conf level)
handler404 = views.handler404

urlpatterns = [
    path('',                   index,               name='home'),
    path('about/',             about,               name='about'),
    path('predict/',           predict_page,        name='predict'),
    path('predict-image/',     predict_image_page,  name='predict_image'),
    path('api/predict/',       api_predict,         name='api_predict'),
    path('api/predict-image/', api_predict_image,   name='api_predict_image'),
    path('api/calibrate-image-threshold/', api_calibrate_image_threshold, name='api_calibrate_image_threshold'),
    path('api/image-calibration-status/', api_image_calibration_status, name='api_image_calibration_status'),
    path('cuda_full/',         cuda_full,           name='cuda_full'),
]

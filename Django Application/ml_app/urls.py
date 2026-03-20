"""project_settings URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from .views import about, index, predict_page, cuda_full, api_predict

app_name = 'ml_app'
handler404 = views.handler404

urlpatterns = [
    path('', index, name='home'),
    path('about/', about, name='about'),
    path('predict/', predict_page, name='predict'),
    path('api/predict/', api_predict, name='api_predict'),
    path('cuda_full/',cuda_full,name='cuda_full'),
]

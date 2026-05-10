"""ForgeGuard URL Configuration"""
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static('/media/videos/', document_root=str(settings.BASE_DIR) + '/uploaded_videos')

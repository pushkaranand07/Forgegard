"""ForgeGuard URL Configuration"""
from django.urls import include, path

# Django only honours error handlers declared in the root URLconf
handler404 = 'api.views.handler404'

# Kept uploads (FORGEGUARD_KEEP_UPLOADS) are never served over HTTP.
urlpatterns = [
    path('', include('api.urls')),
]

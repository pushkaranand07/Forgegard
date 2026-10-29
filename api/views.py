"""
Contains core Django view functions that serve the web UI pages.
The heavy-lifting deep learning logic has been moved to specialized
modules in core/pipeline/ for better maintainability.
"""

import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from .common import error_response
from .forms import VideoUploadForm

# Built by `npm run build` in web/ (see web/vite.config.ts)
SPA_INDEX = os.path.join(settings.PROJECT_DIR, 'frontend', 'static', 'app', 'index.html')

# ─────────────────────────────────────────────
# View Functions (Active UI)
# ─────────────────────────────────────────────

def spa(request):
    """Serve the React single-page app; client-side routing handles the path."""
    try:
        with open(SPA_INDEX, encoding='utf-8') as f:
            return HttpResponse(f.read())
    except FileNotFoundError:
        return HttpResponse(
            '<h1>ForgeGuard UI not built</h1>'
            '<p>Run <code>npm install &amp;&amp; npm run build</code> in <code>web/</code>, '
            'or use the dev server (<code>npm run dev</code>). '
            'The legacy UI is at <a href="/legacy/">/legacy/</a>.</p>',
            status=503,
        )


def video_home(request):
    """Render the video deepfake detection upload page."""
    context = {'form': VideoUploadForm()}
    return render(request, 'video_upload.html', context)


def about(request):
    """Render the About page describing the project and model architecture."""
    # Note: Architecture details are now strictly EfficientNet-B7 and IMDModel.
    return render(request, 'about.html')


def handler404(request, exception):
    """Custom 404 error page (JSON for API paths)."""
    if request.path.startswith('/api/'):
        return error_response('Not found.', 404, 'NOT_FOUND')
    return render(request, '404.html', status=404)


def cuda_full(request):
    """Error page shown when inference fails (e.g. out of CUDA memory)."""
    return render(request, 'cuda_full.html')

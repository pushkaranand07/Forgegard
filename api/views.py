"""
Contains core Django view functions that serve the web UI pages.
The heavy-lifting deep learning logic has been moved to specialized
modules in core/pipeline/ for better maintainability.
"""

from django.shortcuts import render
from .forms import VideoUploadForm

# ─────────────────────────────────────────────
# View Functions (Active UI)
# ─────────────────────────────────────────────

def video_home(request):
    """Render the video deepfake detection upload page."""
    context = {'form': VideoUploadForm()}
    return render(request, 'video_upload.html', context)


def about(request):
    """Render the About page describing the project and model architecture."""
    # Note: Architecture details are now strictly EfficientNet-B7 and IMDModel.
    return render(request, 'about.html')


def handler404(request, exception):
    """Custom 404 error page."""
    return render(request, '404.html', status=404)


def cuda_full(request):
    """Error page shown when inference fails (e.g. out of CUDA memory)."""
    return render(request, 'cuda_full.html')

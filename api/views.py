"""
Non-API views: the React single-page app and the 404 handler.
"""

import os

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_safe

from .common import error_response

# Built by `npm run build` in web/ (see web/vite.config.ts)
SPA_INDEX = os.path.join(settings.PROJECT_DIR, 'frontend', 'static', 'app', 'index.html')


@require_safe
def spa(request):
    """Serve the React single-page app; client-side routing handles the path."""
    try:
        with open(SPA_INDEX, encoding='utf-8') as f:
            return HttpResponse(f.read())
    except FileNotFoundError:
        return HttpResponse(
            '<h1>ForgeGuard UI not built</h1>'
            '<p>Run <code>npm ci &amp;&amp; npm run build</code> in <code>web/</code>, '
            'or use the dev server (<code>npm run dev</code>).</p>',
            status=503,
        )


def handler404(request, exception):
    """JSON 404 for API paths, plain text otherwise."""
    if request.path.startswith('/api/'):
        return error_response('Not found.', 404, 'NOT_FOUND')
    return HttpResponseNotFound('Not found.', content_type='text/plain; charset=utf-8')

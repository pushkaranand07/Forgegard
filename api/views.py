"""
Non-API views: the React single-page app and the 404 handler.
"""

import base64
import hashlib
import os
import re
import threading

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_safe

from .common import error_response

# Built by `npm run build` in web/ (see web/vite.config.ts)
SPA_INDEX = os.path.join(settings.PROJECT_DIR, 'frontend', 'static', 'app', 'index.html')

# Inline <script> blocks (no src attribute). The app's only one sets the colour
# theme before first paint; CSP allows it by its exact hash, nothing else inline.
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)

_spa_cache: dict = {}  # path -> (mtime_ns, html, csp)
_spa_lock = threading.Lock()


def _inline_script_hashes(html: str) -> list:
    return [
        "'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"
        for body in _INLINE_SCRIPT.findall(html)
    ]


def _content_security_policy(html: str) -> str:
    directives = {
        "default-src": ["'self'"],
        "script-src": ["'self'", *_inline_script_hashes(html)],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:"],   # data: favicon and thumbnails, blob: previews
        "media-src": ["'self'", "blob:"],          # local video preview
        "connect-src": ["'self'"],
        "font-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
    return "; ".join(f"{name} {' '.join(values)}" for name, values in directives.items())


def _load_spa():
    """(html, csp) for the built index.html, recomputed when the file changes."""
    mtime = os.stat(SPA_INDEX).st_mtime_ns
    with _spa_lock:
        cached = _spa_cache.get(SPA_INDEX)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]
    with open(SPA_INDEX, encoding='utf-8') as f:
        html = f.read()
    csp = _content_security_policy(html)
    with _spa_lock:
        _spa_cache[SPA_INDEX] = (mtime, html, csp)
    return html, csp


@require_safe
def spa(request):
    """Serve the React single-page app; client-side routing handles the path."""
    try:
        html, csp = _load_spa()
    except FileNotFoundError:
        return HttpResponse(
            '<h1>ForgeGuard UI not built</h1>'
            '<p>Run <code>npm ci &amp;&amp; npm run build</code> in <code>web/</code>, '
            'or use the dev server (<code>npm run dev</code>).</p>',
            status=503,
        )
    response = HttpResponse(html)
    response["Content-Security-Policy"] = csp
    return response


def handler404(request, exception):
    """JSON 404 for API paths, plain text otherwise."""
    if request.path.startswith('/api/'):
        return error_response('Not found.', 404, 'NOT_FOUND')
    return HttpResponseNotFound('Not found.', content_type='text/plain; charset=utf-8')

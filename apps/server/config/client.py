import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBase


def client(request: HttpRequest) -> HttpResponseBase:
    del request
    index = settings.BASE_DIR / "apps" / "client" / "dist" / "index.html"
    if index.exists():
        return HttpResponse(index.read_bytes(), content_type="text/html")
    return HttpResponse(
        "Frame client is not built. Run make client or make client-build.",
        content_type="text/plain",
        status=503,
    )


def static_asset(request: HttpRequest, path: str) -> HttpResponse:
    del request
    root = (settings.BASE_DIR / "apps" / "client" / "dist").resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404
    content_type, _ = mimetypes.guess_type(target.name)
    return HttpResponse(target.read_bytes(), content_type=content_type or "application/octet-stream")


def media(request: HttpRequest, path: str) -> HttpResponse:
    del request
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404
    return HttpResponse(target.read_bytes(), content_type="image/jpeg")

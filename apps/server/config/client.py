from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase


def client(request: HttpRequest) -> HttpResponseBase:
    del request
    index = settings.BASE_DIR / "apps" / "client" / "dist" / "index.html"
    if index.exists():
        return FileResponse(index.open("rb"), content_type="text/html")
    return HttpResponse(
        "Home Movie Poster client is not built. Run make client or make client-build.",
        content_type="text/plain",
        status=503,
    )


def media(request: HttpRequest, path: str) -> FileResponse:
    del request
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404
    return FileResponse(target.open("rb"), content_type="image/jpeg")

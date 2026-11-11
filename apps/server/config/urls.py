from django.urls import path

from apps.server.config.api import api
from apps.server.config.client import client, media

urlpatterns = [
    path("api/", api.urls),
    path("media/<path:path>", media),
    path("", client),
    path("display", client),
    path("admin", client),
]

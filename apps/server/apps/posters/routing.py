from django.urls import path

from .consumers import DisplayConsumer

websocket_urlpatterns = [
    path("api/display/socket", DisplayConsumer.as_asgi())  # type: ignore[reportCallIssue]
]

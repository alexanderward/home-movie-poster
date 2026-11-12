import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.server.config.settings")

django_application = get_asgi_application()


async def application(scope, receive, send):
    """Serve HTTP and quietly reject legacy clients that still request WebSockets."""
    if scope["type"] == "websocket":
        event = await receive()
        if event["type"] == "websocket.connect":
            await send({"type": "websocket.close", "code": 1000})
        return

    await django_application(scope, receive, send)

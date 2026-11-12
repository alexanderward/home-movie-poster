import pytest

from apps.server.config.asgi import application


@pytest.mark.asyncio
async def test_legacy_websocket_request_is_rejected_cleanly():
    messages = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        messages.append(message)

    await application({"type": "websocket"}, receive, send)

    assert messages == [{"type": "websocket.close", "code": 1000}]

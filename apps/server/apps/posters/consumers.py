from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .selectors import display_state


class DisplayConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("display", self.channel_name)
        await self.accept()
        await self.send_state()

    async def disconnect(self, code):
        del code
        await self.channel_layer.group_discard("display", self.channel_name)

    async def display_refresh(self, event):
        del event
        await self.send_state()

    async def send_state(self):
        from channels.db import database_sync_to_async

        state = await database_sync_to_async(display_state)()
        await self.send_json(state.model_dump(mode="json"))

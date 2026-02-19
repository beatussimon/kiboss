import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        print(f"DEBUG: NotificationConsumer connecting, user: {self.user}")
        if self.user.is_anonymous:
            print("DEBUG: NotificationConsumer rejecting anonymous user")
            await self.close()
            return

        self.user_id = str(self.user.id)
        self.room_group_name = f'notifications_{self.user_id}'
        print(f"DEBUG: NotificationConsumer joining group: {self.room_group_name}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print("DEBUG: NotificationConsumer connection accepted")

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Receive notification from room group
    async def notification_message(self, event):
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }))

    # Receive new message alert from room group
    async def new_message(self, event):
        # Send message alert to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'data': event['data']
        }))

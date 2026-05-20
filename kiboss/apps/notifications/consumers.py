import logging

logger = logging.getLogger(__name__)

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Accept the connection FIRST so the handshake completes
        await self.accept()
        logger.debug("DEBUG: NotificationConsumer connection accepted")

        self.user = self.scope.get("user")
        logger.debug(f"DEBUG: NotificationConsumer connecting, user: {self.user}")
        
        if not self.user or self.user.is_anonymous:
            logger.debug("DEBUG: NotificationConsumer rejecting anonymous user")
            await self.send(text_data=json.dumps({'error': 'Authentication required'}))
            # DO NOT close the socket here. Let the frontend close it to prevent TCP RST 1006 error.
            return

        self.user_id = str(self.user.id)
        self.room_group_name = f'notifications_{self.user_id}'
        logger.debug(f"DEBUG: NotificationConsumer joining group: {self.room_group_name}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Receive notification from room group
    async def notification_message(self, event):
        try:
            logger.debug(f"DEBUG: NotificationConsumer RECEIVED notification_message for {self.room_group_name}")
            # Send notification to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'data': event['data']
            }))
        except Exception as e:
            logger.debug(f"DEBUG: NotificationConsumer failed to send notification: {str(e)}")

    # Receive new message alert from room group
    async def new_message(self, event):
        try:
            logger.debug(f"DEBUG: NotificationConsumer RECEIVED new_message for {self.room_group_name}")
            # Send message alert to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'data': event['data']
            }))
        except Exception as e:
            logger.debug(f"DEBUG: NotificationConsumer failed to send new_message: {str(e)}")

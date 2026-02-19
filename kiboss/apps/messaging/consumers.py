import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group_name = f'chat_{self.thread_id}'

        # Verify user is a participant of the thread
        if not await self.is_participant(self.thread_id, self.user):
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_typing',
                    'user_id': str(self.user.id),
                    'is_typing': text_data_json.get('is_typing', False)
                }
            )
        elif message_type == 'read_receipt':
            message_ids = text_data_json.get('message_ids', [])
            await self.mark_messages_as_read(message_ids)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_read_receipt',
                    'user_id': str(self.user.id),
                    'message_ids': message_ids
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'data': event['data']
        }))

    async def chat_typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'is_typing': event['is_typing']
        }))

    async def chat_read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id'],
            'message_ids': event['message_ids']
        }))

    @database_sync_to_async
    def is_participant(self, thread_id, user):
        from kiboss.apps.messaging.models import Thread
        try:
            thread = Thread.objects.get(id=thread_id)
            return thread.participants.filter(id=user.id).exists()
        except (Thread.DoesNotExist, ValueError):
            return False

    @database_sync_to_async
    def mark_messages_as_read(self, message_ids):
        from kiboss.apps.messaging.models import Message, MessageReadReceipt
        messages = Message.objects.filter(id__in=message_ids, thread_id=self.thread_id).exclude(sender=self.user)
        for msg in messages:
            MessageReadReceipt.objects.get_or_create(message=msg, user=self.user)

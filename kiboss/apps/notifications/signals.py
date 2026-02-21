from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from kiboss.apps.notifications.models import Notification
from kiboss.apps.notifications.serializers import NotificationSerializer

@receiver(post_save, sender=Notification)
def broadcast_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                import json
                from rest_framework.renderers import JSONRenderer
                notif_data = NotificationSerializer(instance).data
                notif_data_json = json.loads(JSONRenderer().render(notif_data))
                
                user_id_str = str(instance.user.id)
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{user_id_str}',
                    {
                        'type': 'notification_message',
                        'data': notif_data_json
                    }
                )
            except Exception as e:
                import logging
                logger = logging.getLogger('kiboss')
                logger.error(f"Failed to broadcast notification: {str(e)}")

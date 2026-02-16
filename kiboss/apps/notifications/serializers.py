"""
Serializers for Notifications API
"""
from rest_framework import serializers
from kiboss.apps.notifications.models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'category', 'notification_type', 'title', 'message',
            'action_url', 'status', 'channels',
            'sent_at', 'delivered_at', 'read_at',
            'failure_reason', 'retry_count',
            'booking', 'ride', 'priority',
            'expires_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'category', 'notification_type', 'title', 'message',
            'status', 'channels',
            'sent_at', 'delivered_at', 'read_at',
            'failure_reason', 'retry_count',
            'booking', 'ride', 'priority',
            'expires_at', 'created_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences."""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'email_enabled', 'push_enabled', 'sms_enabled',
            'categories', 'quiet_hours_enabled',
            'quiet_hours_start', 'quiet_hours_end'
        ]
        read_only_fields = ['id']


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications (admin only)."""
    
    class Meta:
        model = Notification
        fields = [
            'user', 'category', 'notification_type', 'title', 'message',
            'action_url', 'channels', 'priority', 'expires_at'
        ]

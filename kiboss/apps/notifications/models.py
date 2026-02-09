"""
Notification Models for KIBOSS - Event-Driven Notifications

Features:
- Event-driven
- Persisted
- User-configurable
- Async via Celery
- Guaranteed delivery locally
"""

import uuid
from django.db import models
from django.conf import settings


class NotificationCategory(models.TextChoices):
    """Notification category."""
    BOOKING = 'BOOKING', 'Booking'
    RIDE = 'RIDE', 'Ride'
    PAYMENT = 'PAYMENT', 'Payment'
    CONTRACT = 'CONTRACT', 'Contract'
    MESSAGE = 'MESSAGE', 'Message'
    RATING = 'RATING', 'Rating'
    SYSTEM = 'SYSTEM', 'System'
    MARKETING = 'MARKETING', 'Marketing'


class NotificationChannel(models.TextChoices):
    """Notification channel."""
    IN_APP = 'IN_APP', 'In-App'
    EMAIL = 'EMAIL', 'Email'
    PUSH = 'PUSH', 'Push Notification'
    SMS = 'SMS', 'SMS'


class NotificationStatus(models.TextChoices):
    """Notification delivery status."""
    PENDING = 'PENDING', 'Pending'
    SENT = 'SENT', 'Sent'
    DELIVERED = 'DELIVERED', 'Delivered'
    READ = 'READ', 'Read'
    FAILED = 'FAILED', 'Failed'


class Notification(models.Model):
    """Notification model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Category and type
    category = models.CharField(max_length=20, choices=NotificationCategory.choices)
    notification_type = models.CharField(max_length=100)
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Action URL
    action_url = models.CharField(max_length=500, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    
    # Channels to deliver
    channels = models.JSONField(default=list)
    
    # Delivery tracking
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # Failure tracking
    failure_reason = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Context (optional)
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notifications'
    )
    ride = models.ForeignKey(
        'rides.Ride',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notifications'
    )
    
    # Priority
    priority = models.PositiveIntegerField(default=0)
    
    # Expires at
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"Notification {self.id}: {self.title}"
    
    def mark_read(self):
        """Mark notification as read."""
        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.save()


class NotificationPreference(models.Model):
    """User notification preferences."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Channel preferences (JSON)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    # Category preferences (JSON)
    categories = models.JSONField(default=dict, blank=True)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(blank=True, null=True)
    quiet_hours_end = models.TimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f"Notification preferences for {self.user.email}"


from django.utils import timezone

"""
Messaging Models for KIBOSS - Context-Aware Messaging

Features:
- Pre-booking inquiries
- Booking-bound threads
- Ride-bound threads
- Open DMs (rate-limited)
- Admin moderation
- Auto-lock after completion
- Immutable messages
- Attachments support
- Abuse protection
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

from kiboss.apps.common.validators import validate_file_size, validate_attachment_extension


class ThreadType(models.TextChoices):
    """Thread type enumeration."""
    INQUIRY = 'INQUIRY', 'Pre-booking Inquiry'
    BOOKING = 'BOOKING', 'Booking Discussion'
    RIDE = 'RIDE', 'Ride Discussion'
    DISPUTE = 'DISPUTE', 'Dispute Resolution'
    DIRECT = 'DIRECT', 'Direct Message'
    SUPPORT = 'SUPPORT', 'Support'


class ContextType(models.TextChoices):
    """Allowed contextual anchors for a thread."""
    ASSET = 'ASSET', 'Asset'
    BOOKING = 'BOOKING', 'Booking'
    RIDE = 'RIDE', 'Ride'


class ThreadStatus(models.TextChoices):
    """Thread status."""
    OPEN = 'OPEN', 'Open'
    LOCKED = 'LOCKED', 'Locked'
    CLOSED = 'CLOSED', 'Closed'
    ARCHIVED = 'ARCHIVED', 'Archived'


class MessageStatus(models.TextChoices):
    """Message delivery status."""
    SENT = 'SENT', 'Sent'
    DELIVERED = 'DELIVERED', 'Delivered'
    READ = 'READ', 'Read'


class Thread(models.Model):
    """
    Conversation thread for messaging.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Thread type
    thread_type = models.CharField(
        max_length=20,
        choices=ThreadType.choices
    )
    
    # Participants
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='message_threads'
    )
    
    # Context (optional foreign key depending on type)
    context_type = models.CharField(
        max_length=20,
        choices=ContextType.choices,
        blank=True,
        null=True
    )
    context_id = models.UUIDField(blank=True, null=True)

    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='threads'
    )
    ride = models.ForeignKey(
        'rides.Ride',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='threads'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=ThreadStatus.choices,
        default=ThreadStatus.OPEN
    )
    
    # Subject/topic
    subject = models.CharField(max_length=255, blank=True)
    
    # Auto-lock settings
    auto_lock_after_completion = models.BooleanField(default=True)
    locked_at = models.DateTimeField(blank=True, null=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='locked_threads'
    )
    
    # Moderation
    is_flagged = models.BooleanField(default=False)
    flagged_reason = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='moderated_threads'
    )
    
    # Statistics
    message_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'message_threads'
        verbose_name = 'Message Thread'
        verbose_name_plural = 'Message Threads'
        indexes = [
            models.Index(fields=['thread_type']),
            models.Index(fields=['status']),
            models.Index(fields=['context_type', 'context_id']),
        ]
    
    def __str__(self):
        return f"Thread {self.id} - {self.get_thread_type_display()}"
    
    def lock(self, user):
        """Lock the thread."""
        self.status = ThreadStatus.LOCKED
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save()
    
    def unlock(self, user):
        """Unlock the thread (admin only)."""
        self.status = ThreadStatus.OPEN
        self.locked_at = None
        self.locked_by = None
        self.save()


class Message(models.Model):
    """
    Individual message in a thread.
    Messages are immutable after sending.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Sender
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_messages'
    )
    
    # Content
    content = models.TextField(max_length=10000)
    content_type = models.CharField(max_length=20, default='text/plain')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.SENT
    )
    
    # Read receipts
    read_at = models.DateTimeField(blank=True, null=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='read_messages',
        through='MessageReadReceipt'
    )
    
    # Deletion (soft delete)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messages'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            models.Index(fields=['sender']),
        ]
    
    def __str__(self):
        return f"Message {self.id} from {self.sender.email}"
    
    def soft_delete(self):
        """Soft delete the message."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class MessageReadReceipt(models.Model):
    """Track read receipts for messages."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_receipts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_read_receipts'
    )
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_read_receipts'
        unique_together = ['message', 'user']
    
    def __str__(self):
        return f"{self.user.email} read {self.message.id} at {self.read_at}"


class MessageAttachment(models.Model):
    """Attachments for messages."""
    
    ATTACHMENT_TYPES = [
        ('IMAGE', 'Image'),
        ('DOCUMENT', 'Document'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    file = models.FileField(upload_to='message_attachments/%Y/%m/', validators=[validate_file_size, validate_attachment_extension])
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPES)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # bytes
    
    # Security: virus scan status
    is_safe = models.BooleanField(default=True)
    scan_error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'message_attachments'
        verbose_name = 'Message Attachment'
        verbose_name_plural = 'Message Attachments'
    
    def __str__(self):
        return f"Attachment: {self.file_name}"


class MessageRateLimit(models.Model):
    """Rate limiting for messaging."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_rate_limits'
    )
    
    # Rate limit tracking
    message_count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
    
    class Meta:
        db_table = 'message_rate_limits'
        verbose_name = 'Message Rate Limit'
        verbose_name_plural = 'Message Rate Limits'
    
    def __str__(self):
        return f"Rate limit for {self.user.email}"


# Import timezone
from django.utils import timezone

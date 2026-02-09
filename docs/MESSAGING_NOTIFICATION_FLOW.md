# Messaging & Notification Flow for KIBOSS

This document describes the context-aware messaging system and event-driven notification flow for KIBOSS.

---

## 1. Messaging System Overview

### 1.1 Thread Types

| Type | Description | Participants | Auto-Lock |
|------|-------------|--------------|-----------|
| **INQUIRY** | Pre-booking questions | Renter, Owner | After booking |
| **BOOKING** | Booking-specific discussion | Renter, Owner | After completion |
| **RIDE** | Ride-sharing discussion | Passenger, Driver | After completion |
| **DISPUTE** | Dispute resolution | Renter, Owner, Support | Never (admin close) |
| **DIRECT** | Open DMs | Any 2 users | After 72h inactivity |
| **SUPPORT** | Support tickets | User, Support | Never (admin close) |

### 1.2 Thread Status

| Status | Description |
|--------|-------------|
| **OPEN** | Active conversation |
| **LOCKED** | No new messages allowed (read-only) |
| **CLOSED** | Archived (admin action) |
| **ARCHIVED** | Auto-archived after completion |

---

## 2. Messaging Flow

### 2.1 Thread Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        THREAD CREATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER                                                                            │
│      │                                                                        │
│      ▼                                                                        │
│   ┌───────────────┐                                                         │
│   │ Create Thread │                                                         │
│   │ Request       │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Validate      │ ─── Invalid? ───► 400 Bad Request                       │
│   │ Request       │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Check Rate    │ ─── Exceeded? ───► 429 Too Many Requests                │
│   │ Limits        │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Create Thread │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Create Initial│                                                         │
│   │ Message       │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Send WebSocket│                                                         │
│   │ Notification  │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Return Thread │                                                         │
│   │ with Messages │                                                         │
│   └───────────────┘                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Message Sending Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MESSAGE SENDING FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER                                                                            │
│      │                                                                        │
│      ▼                                                                        │
│   ┌───────────────┐                                                         │
│   │ Send Message  │                                                         │
│   │ Request       │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Validate      │ ─── Thread locked? ───► 403 Forbidden                    │
│   │ Thread Status │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Check Rate    │ ─── Exceeded? ───► 429 Too Many Requests                │
│   │ Limits        │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Check Content │ ─── Abuse detected? ───► Flag + Warn                     │
│   │ Safety        │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Create Message│                                                         │
│   │ (Immutable)   │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Update Thread │                                                         │
│   │ Stats         │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Create Read    │                                                         │
│   │ Receipts      │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Send WebSocket│                                                         │
│   │ to Participants│                                                        │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Queue In-App   │                                                         │
│   │ Notification   │                                                         │
│   └───────────────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │ Return Message│                                                         │
│   └───────────────┘                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Messaging Implementation

### 3.1 Service Layer

```python
# kiboss/apps/messaging/services.py

import uuid
from django.db import transaction
from django.utils import timezone
from kiboss.apps.messaging.models import Thread, Message, MessageStatus
from kiboss.apps.common.rate_limiting import rate_limiter


class MessagingService:
    """Service for messaging operations."""
    
    @classmethod
    def create_thread(cls, creator, thread_type, subject=None, 
                     asset_id=None, ride_id=None, initial_message=None):
        """
        Create a new thread with initial message.
        
        Args:
            creator: User creating the thread
            thread_type: Type of thread
            subject: Thread subject
            asset_id: Optional asset ID
            ride_id: Optional ride ID
            initial_message: First message content
            
        Returns:
            Thread object
        """
        # Check rate limits
        is_allowed, _, _ = rate_limiter.check_messaging_rate_limit(str(creator.id))
        if not is_allowed:
            raise RateLimitExceededError("Messaging rate limit exceeded")
        
        with transaction.atomic():
            # Create thread
            thread = Thread.objects.create(
                thread_type=thread_type,
                subject=subject or '',
                asset_id=asset_id,
                ride_id=ride_id
            )
            
            # Add participants
            thread.participants.add(creator)
            
            # Add other participant based on thread type
            if asset_id:
                from kiboss.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id)
                thread.participants.add(asset.owner)
            
            if ride_id:
                from kiboss.apps.rides.models import Ride
                ride = Ride.objects.get(id=ride_id)
                thread.participants.add(ride.driver)
            
            # Create initial message if provided
            if initial_message:
                cls.send_message(thread, creator, initial_message)
            
            return thread
    
    @classmethod
    def send_message(cls, thread, sender, content, attachments=None):
        """
        Send a message in a thread.
        
        Messages are immutable after sending.
        
        Args:
            thread: Thread object
            sender: User sending message
            content: Message content
            attachments: Optional attachments
            
        Returns:
            Message object
        """
        # Validate thread status
        if thread.status == ThreadStatus.LOCKED:
            raise ThreadLockedError("Cannot send messages to locked thread")
        
        if thread.status == ThreadStatus.CLOSED:
            raise ThreadClosedError("Thread is closed")
        
        # Verify sender is participant
        if not thread.participants.filter(id=sender.id).exists():
            raise NotParticipantError("Sender is not a participant")
        
        # Check rate limits
        is_allowed, _, _ = rate_limiter.check_messaging_rate_limit(str(sender.id))
        if not is_allowed:
            raise RateLimitExceededError("Messaging rate limit exceeded")
        
        with transaction.atomic():
            # Create message
            message = Message.objects.create(
                thread=thread,
                sender=sender,
                content=content,
                content_type='text/plain',
                status=MessageStatus.SENT
            )
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    MessageAttachment.objects.create(
                        message=message,
                        file=attachment['file'],
                        file_type=attachment.get('type', 'DOCUMENT'),
                        file_name=attachment['name'],
                        file_size=attachment['size']
                    )
            
            # Update thread
            thread.message_count += 1
            thread.save(update_fields=['message_count', 'updated_at'])
            
            # Create read receipts for other participants
            for participant in thread.participants.exclude(id=sender.id):
                MessageReadReceipt.objects.create(
                    message=message,
                    user=participant
                )
            
            return message
    
    @classmethod
    def mark_thread_read(cls, thread, user):
        """Mark all messages in thread as read."""
        Message.objects.filter(
            thread=thread,
            read_receipts__user=user
        ).exclude(
            read_receipts__user=user
        ).update(status=MessageStatus.READ)
        
        MessageReadReceipt.objects.filter(
            message__thread=thread,
            user=user,
            read_at__isnull=True
        ).update(read_at=timezone.now())
    
    @classmethod
    def lock_thread(cls, thread, user, reason=''):
        """
        Lock a thread (automatic or manual).
        
        Automatic lock triggers:
        - INQUIRY: After booking is created
        - BOOKING: After booking is completed
        - RIDE: After ride is completed
        """
        thread.status = ThreadStatus.LOCKED
        thread.locked_at = timezone.now()
        thread.locked_by = user
        thread.save()
    
    @classmethod
    def flag_thread(cls, thread, user, reason):
        """Flag thread for moderation."""
        thread.is_flagged = True
        thread.flagged_reason = reason
        thread.save()


class RateLimitExceededError(Exception):
    pass


class ThreadLockedError(Exception):
    pass


class ThreadClosedError(Exception):
    pass


class NotParticipantError(Exception):
    pass
```

### 3.2 WebSocket Consumers

```python
# kiboss/apps/messaging/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone


class MessagingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time messaging.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Get thread ID from URL
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        
        # Join thread group
        self.group_name = f'thread_{self.thread_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'typing':
            await self.handle_typing(data)
        elif message_type == 'read':
            await self.handle_read(data)
    
    async def handle_typing(self, data):
        """Handle typing indicator."""
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'messaging.typing',
                'user_id': str(self.user.id),
                'thread_id': self.thread_id
            }
        )
    
    async def handle_read(self, data):
        """Handle read receipt via WebSocket."""
        message_ids = data.get('message_ids', [])
        
        await sync_to_async(MessagingService.mark_thread_read)(
            thread_id=self.thread_id,
            user=self.user
        )
    
    async def message_new(self, event):
        """Handle new message from channel layer."""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
    
    async def typing(self, event):
        """Send typing indicator to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id']
        }))
```

---

## 4. Notification System

### 4.1 Notification Categories

| Category | Description |
|----------|-------------|
| **BOOKING** | Booking-related notifications |
| **RIDE** | Ride-sharing notifications |
| **PAYMENT** | Payment notifications |
| **CONTRACT** | Contract notifications |
| **MESSAGE** | New message notifications |
| **RATING** | Rating notifications |
| **SYSTEM** | System announcements |

### 4.2 Notification Channels

| Channel | Description | Priority |
|---------|-------------|----------|
| **IN_APP** | In-app notification center | 1 |
| **EMAIL** | Email notification | 2 |
| **PUSH** | Push notification | 3 |
| **SMS** | SMS notification | 4 |

---

## 5. Notification Flow

### 5.1 Event-Driven Notification Creation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION CREATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   EVENT OCCURS (e.g., Booking Created)                                       │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Create Event │                                                           │
│   │ Record       │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Determine     │                                                           │
│   │ Recipients    │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Get User      │                                                           │
│   │ Preferences   │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Check Quiet   │                                                           │
│   │ Hours         │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ├───── In quiet hours ─────► Queue for later                        │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Create        │                                                           │
│   │ Notification  │                                                           │
│   │ Records       │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Send to       │                                                           │
│   │ Celery Queue  │                                                           │
│   └───────────────┘                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Notification Delivery Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION DELIVERY FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CELERY WORKER                                                               │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Fetch Pending │                                                           │
│   │ Notifications │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ For Each      │                                                           │
│   │ Notification  │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Get Channels  │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ For Each      │                                                           │
│   │ Channel       │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Send via      │                                                           │
│   │ Channel       │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ Update Status │                                                           │
│   └───────┬───────┘                                                           │
│           │                                                                   │
│           ▼                                                                   │
│   ┌───────────────┐                                                           │
│   │ WebSocket     │                                                           │
│   │ Push (In-App) │                                                           │
│   └───────────────┘                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Notification Implementation

### 6.1 Notification Service

```python
# kiboss/apps/notifications/services.py

import uuid
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from kiboss.apps.notifications.models import (
    Notification, NotificationStatus, NotificationChannel,
    NotificationPreference
)


class NotificationService:
    """Service for notification operations."""
    
    # Event type to notification mapping
    EVENT_NOTIFICATION_MAP = {
        'booking.created': {
            'category': 'BOOKING',
            'notification_type': 'booking_created',
            'title': 'New Booking Request',
            'message': 'You have a new booking request for {asset_name}',
            'channels': ['IN_APP', 'EMAIL']
        },
        'booking.confirmed': {
            'category': 'BOOKING',
            'notification_type': 'booking_confirmed',
            'title': 'Booking Confirmed',
            'message': 'Your booking for {asset_name} has been confirmed',
            'channels': ['IN_APP', 'EMAIL']
        },
        'booking.expired': {
            'category': 'BOOKING',
            'notification_type': 'booking_expired',
            'title': 'Booking Expired',
            'message': 'Your booking for {asset_name} has expired',
            'channels': ['IN_APP']
        },
        'message.received': {
            'category': 'MESSAGE',
            'notification_type': 'new_message',
            'title': 'New Message',
            'message': 'You have a new message from {sender_name}',
            'channels': ['IN_APP', 'PUSH']
        },
        'contract.pending': {
            'category': 'CONTRACT',
            'notification_type': 'contract_pending',
            'title': 'Contract Awaiting Signature',
            'message': 'Please review and sign your contract',
            'channels': ['IN_APP', 'EMAIL']
        },
        'payment.escrow_released': {
            'category': 'PAYMENT',
            'notification_type': 'payment_released',
            'title': 'Payment Released',
            'message': 'Your payment of {amount} has been released',
            'channels': ['IN_APP', 'EMAIL']
        },
        'rating.received': {
            'category': 'RATING',
            'notification_type': 'new_rating',
            'title': 'You received a rating',
            'message': 'You received a {rating}-star rating',
            'channels': ['IN_APP']
        },
        'ride.departing': {
            'category': 'RIDE',
            'notification_type': 'ride_departing',
            'title': 'Ride Departing Soon',
            'message': 'Your ride {route_name} departs in {minutes} minutes',
            'channels': ['IN_APP', 'PUSH']
        }
    }
    
    @classmethod
    def create_notification(cls, event_type, recipient, context=None, 
                           channels=None, priority=0, action_url='',
                           booking=None, ride=None):
        """
        Create a notification from an event.
        
        Args:
            event_type: Type of event
            recipient: User to notify
            context: Event context data
            channels: Override channels
            priority: Notification priority
            action_url: URL to navigate to
            booking: Related booking
            ride: Related ride
        """
        event_config = cls.EVENT_NOTIFICATION_MAP.get(event_type, {})
        
        if not event_config:
            return None
        
        # Check user preferences
        try:
            prefs = NotificationPreference.objects.get(user=recipient)
        except NotificationPreference.DoesNotExist:
            prefs = NotificationPreference.objects.create(user=recipient)
        
        # Determine channels
        if channels is None:
            channels = event_config.get('channels', ['IN_APP'])
        
        # Filter by preferences
        category = event_config.get('category', 'SYSTEM')
        category_prefs = prefs.categories.get(category, {})
        
        final_channels = []
        for channel in channels:
            if channel == 'IN_APP':
                final_channels.append(channel)
            elif channel == 'EMAIL' and prefs.email_enabled:
                final_channels.append(channel)
            elif channel == 'PUSH' and prefs.push_enabled:
                final_channels.append(channel)
            elif channel == 'SMS' and prefs.sms_enabled:
                final_channels.append(channel)
        
        if not final_channels:
            return None
        
        # Check quiet hours
        if prefs.quiet_hours_enabled:
            now = timezone.now().time()
            if prefs.quiet_hours_start <= now <= prefs.quiet_hours_end:
                # Queue for later
                final_channels = ['IN_APP']  # Only in-app
        
        # Build message with context
        message_template = event_config.get('message', '')
        message = message_template.format(**context) if context else message_template
        
        title_template = event_config.get('title', '')
        title = title_template.format(**context) if context else title_template
        
        with transaction.atomic():
            notification = Notification.objects.create(
                user=recipient,
                category=event_config.get('category', 'SYSTEM'),
                notification_type=event_config.get('notification_type', event_type),
                title=title,
                message=message,
                action_url=action_url,
                channels=final_channels,
                priority=priority,
                booking=booking,
                ride=ride
            )
        
        return notification
    
    @classmethod
    def send_booking_created_notification(cls, booking):
        """Send notification when booking is created."""
        # Notify owner
        cls.create_notification(
            event_type='booking.created',
            recipient=booking.asset.owner,
            context={
                'asset_name': booking.asset.name,
                'renter_name': booking.renter.get_full_name()
            },
            action_url=f'/bookings/{booking.id}/',
            booking=booking
        )
    
    @classmethod
    def send_message_notification(cls, thread, message):
        """Send notification for new message."""
        for participant in thread.participants.exclude(id=message.sender_id):
            cls.create_notification(
                event_type='message.received',
                recipient=participant,
                context={
                    'sender_name': message.sender.get_full_name(),
                    'thread_type': thread.get_thread_type_display()
                },
                action_url=f'/messages/{thread.id}/',
                priority=1
            )
    
    @classmethod
    def send_booking_reminder_notification(cls, booking):
        """Send booking reminder."""
        # Notify renter
        cls.create_notification(
            event_type='booking.reminder',
            recipient=booking.renter,
            context={
                'asset_name': booking.asset.name,
                'start_time': booking.start_time.strftime('%B %d at %I:%M %p')
            },
            action_url=f'/bookings/{booking.id}/',
            booking=booking
        )
```

### 6.2 Channel Implementations

```python
# kiboss/apps/notifications/channels.py

from django.core.mail import send_mail
from django.template.loader import render_to_string
from kiboss.apps.notifications.models import NotificationChannel


class EmailNotificationService:
    """Email notification channel."""
    
    @classmethod
    def send(cls, notification):
        """Send email notification."""
        # Render email template
        html_content = render_to_string(
            'notifications/email.html',
            {'notification': notification}
        )
        
        # Send email
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email='noreply@kiboss.local',
            recipient_list=[notification.user.email],
            html_message=html_content
        )
        
        # Update notification
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save()


class PushNotificationService:
    """Push notification channel (Web)."""
    
    @classmethod
    def send(cls, notification):
        """Send push notification."""
        # Get user devices
        from kiboss.apps.users.models import Device
        
        devices = Device.objects.filter(
            user=notification.user,
            device_type='web',
            is_active=True
        )
        
        for device in devices:
            # Send to service worker
            cls._send_to_device(device.device_token, {
                'title': notification.title,
                'body': notification.message,
                'icon': '/static/icons/notification-icon.png',
                'url': notification.action_url
            })
        
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save()
    
    @classmethod
    def _send_to_device(cls, token, payload):
        """Send to specific device (placeholder for actual implementation)."""
        # Would use webpush or similar library
        pass


class InAppNotificationService:
    """In-app notification channel."""
    
    @classmethod
    def send(cls, notification):
        """Store in-app notification."""
        # Notification is already stored in database
        # Just update status to sent
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save()
        
        # Send WebSocket message
        from channels.layers import channel_layer
        from asgiref.sync import async_to_sync
        
        async_to_sync(channel_layer.group_send)(
            f'user_{notification.user_id}',
            {
                'type': 'notification.new',
                'notification': {
                    'id': str(notification.id),
                    'title': notification.title,
                    'message': notification.message,
                    'action_url': notification.action_url,
                    'created_at': notification.created_at.isoformat()
                }
            }
        )
```

---

## 7. Abuse Protection

### 7.1 Rate Limiting

| Action | Limit | Window |
|--------|-------|--------|
| Messages sent | 100 | Per hour |
| Threads created | 50 | Per hour |
| Messages reported | 10 | Per day |

### 7.2 Content Safety

```python
# kiboss/apps/messaging/safety.py

class ContentSafetyService:
    """Content safety and abuse prevention."""
    
    # Keywords that trigger flagging
    FLAGGED_KEYWORDS = [
        'spam',
        'scam',
        # ... more keywords
    ]
    
    @classmethod
    def check_content(cls, content):
        """Check content for abuse patterns."""
        # Check for flagged keywords
        for keyword in cls.FLAGGED_KEYWORDS:
            if keyword in content.lower():
                return {'flagged': True, 'reason': f'Keyword detected: {keyword}'}
        
        # Check for excessive caps
        if cls._is_excessive_caps(content):
            return {'flagged': True, 'reason': 'Excessive capitalization'}
        
        # Check for spam patterns
        if cls._is_spam_pattern(content):
            return {'flagged': True, 'reason': 'Spam pattern detected'}
        
        return {'flagged': False}
    
    @classmethod
    def _is_excessive_caps(cls, content):
        """Check if content has excessive capitalization."""
        if len(content) < 20:
            return False
        caps_ratio = sum(1 for c in content if c.isupper()) / len(content)
        return caps_ratio > 0.7
    
    @classmethod
    def _is_spam_pattern(cls, content):
        """Check for common spam patterns."""
        # Check for URL patterns
        if 'http://' in content or 'https://' in content:
            return True
        # Check for excessive emojis
        if content.count('' ) > 10:
            return True
        return False
```

---

## 8. Auto-Lock Rules

### 8.1 Automatic Thread Locking

| Thread Type | Trigger | Lock Time |
|-------------|---------|-----------|
| INQUIRY | Booking created for same asset | Immediate |
| BOOKING | Booking status = COMPLETED | 24h after completion |
| RIDE | Ride status = COMPLETED | 24h after completion |
| DISPUTE | Never (admin only) | - |
| SUPPORT | Never (admin only) | - |

```python
# kiboss/apps/messaging/autolock.py

class ThreadAutoLockService:
    """Automatic thread locking service."""
    
    @classmethod
    def check_and_lock_threads(cls):
        """
        Check for threads that need to be locked.
        
        Scheduled task runs every 15 minutes.
        """
        from kiboss.apps.messaging.models import Thread, ThreadStatus
        from kiboss.apps.bookings.models import Booking, BookingStatus
        from kiboss.apps.rides.models import Ride, RideStatus
        
        # Lock INQUIRY threads when booking is created
        inquiry_threads = Thread.objects.filter(
            thread_type='INQUIRY',
            status=ThreadStatus.OPEN
        ).exclude(
            booking__isnull=True
        )
        
        for thread in inquiry_threads:
            if thread.booking and thread.booking.status not in [
                BookingStatus.PENDING, BookingStatus.CANCELLED
            ]:
                cls.lock_thread(thread, 'SYSTEM')
        
        # Lock BOOKING threads after completion
        booking_threads = Thread.objects.filter(
            thread_type='BOOKING',
            status=ThreadStatus.OPEN
        ).filter(
            booking__status=BookingStatus.COMPLETED,
            booking__completed_at__lt=timezone.now() - timedelta(hours=24)
        )
        
        for thread in booking_threads:
            cls.lock_thread(thread, 'SYSTEM')
        
        # Lock RIDE threads after completion
        ride_threads = Thread.objects.filter(
            thread_type='RIDE',
            status=ThreadStatus.OPEN
        ).filter(
            ride__status=RideStatus.COMPLETED,
            ride__actual_arrival__lt=timezone.now() - timedelta(hours=24)
        )
        
        for thread in ride_threads:
            cls.lock_thread(thread, 'SYSTEM')
    
    @classmethod
    def lock_thread(cls, thread, actor):
        """Lock a thread."""
        thread.status = ThreadStatus.LOCKED
        thread.locked_at = timezone.now()
        thread.save()
```

---

## 9. WebSocket Events

### 9.1 Event Types

| Event Type | Direction | Description |
|------------|-----------|-------------|
| `messaging.new_message` | Server → Client | New message received |
| `messaging.typing` | Bidirectional | User is typing |
| `messaging.read` | Client → Server | Mark messages read |
| `messaging.read_receipt` | Server → Client | Read receipt update |
| `notification.new` | Server → Client | New notification |
| `user.online` | Server → Client | User came online |
| `user.offline` | Server → Client | User went offline |

### 9.2 WebSocket Message Formats

**New Message:**
```json
{
    "type": "messaging.new_message",
    "message": {
        "id": "uuid",
        "thread_id": "uuid",
        "sender": {
            "id": "uuid",
            "first_name": "John",
            "avatar": "/media/..."
        },
        "content": "Hello!",
        "created_at": "2024-01-20T10:30:00Z",
        "attachments": []
    }
}
```

**Typing Indicator:**
```json
{
    "type": "messaging.typing",
    "thread_id": "uuid",
    "user_id": "uuid"
}
```

**New Notification:**
```json
{
    "type": "notification.new",
    "notification": {
        "id": "uuid",
        "title": "New Booking",
        "message": "You have a new booking",
        "action_url": "/bookings/123",
        "created_at": "2024-01-20T10:30:00Z"
    }
}
```

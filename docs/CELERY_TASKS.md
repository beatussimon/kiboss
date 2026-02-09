# Celery Task Definitions for KIBOSS

This document defines all Celery tasks for asynchronous processing in KIBOSS.

---

## 1. Task Configuration

### 1.1 Celery Configuration

```python
# kiboss/celery.py

import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')

app = Celery('kiboss')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Beat schedule configuration
app.conf.beat_schedule = {
    # Booking tasks
    'expire-pending-bookings': {
        'task': 'bookings.tasks.expire_pending_bookings',
        'schedule': 60.0,  # Every minute
    },
    'check-active-bookings': {
        'task': 'bookings.tasks.check_active_bookings',
        'schedule': 300.0,  # Every 5 minutes
    },
    'process-completed-bookings': {
        'task': 'bookings.tasks.process_completed_bookings',
        'schedule': 300.0,  # Every 5 minutes
    },
    'check-no-shows': {
        'task': 'bookings.tasks.check_no_shows',
        'schedule': 60.0,  # Every minute
    },
    
    # Ride tasks
    'generate-ride-schedules': {
        'task': 'rides.tasks.generate_scheduled_rides',
        'schedule': 3600.0,  # Every hour
    },
    'process-ride-departures': {
        'task': 'rides.tasks.process_ride_departures',
        'schedule': 60.0,  # Every minute
    },
    
    # Notification tasks
    'send-pending-notifications': {
        'task': 'notifications.tasks.send_pending_notifications',
        'schedule': 30.0,  # Every 30 seconds
    },
    
    # Rating tasks
    'reveal-mutual-ratings': {
        'task': 'ratings.tasks.reveal_mutual_ratings',
        'schedule': 300.0,  # Every 5 minutes
    },
    
    # Cleanup tasks
    'cleanup-expired-locks': {
        'task': 'common.tasks.cleanup_expired_locks',
        'schedule': 3600.0,  # Every hour
    },
}

app.conf.timezone = 'UTC'
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.result_expires = 3600  # 1 hour
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
```

---

## 2. Booking Tasks

### 2.1 Expire Pending Bookings

```python
# kiboss/apps/bookings/tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def expire_pending_bookings(self):
    """
    Expire pending bookings that have not been paid within the timeout period.
    
    Schedule: Every 1 minute
    
    Process:
    1. Find all PENDING bookings older than 15 minutes
    2. For each booking:
       - Update status to EXPIRED
       - Create status transition record
       - Release any held payment authorization
       - Send notification to renter and owner
       - Update asset availability
    """
    from kiboss.apps.bookings.models import Booking, BookingStatus
    from kiboss.apps.bookings.services import BookingLockService
    from kiboss.apps.notifications.services import NotificationService
    
    expired_count = 0
    timeout_minutes = 15
    
    pending_bookings = Booking.objects.filter(
        status=BookingStatus.PENDING,
        created_at__lt=timezone.now() - timedelta(minutes=timeout_minutes)
    ).select_related('asset', 'renter')
    
    for booking in pending_bookings:
        try:
            with BookingLockService.with_booking_lock(booking.id):
                # Re-check status (may have changed)
                booking.refresh_from_db()
                if booking.status != BookingStatus.PENDING:
                    continue
                
                # Transition to EXPIRED
                booking.transition_to(
                    BookingStatus.EXPIRED,
                    actor_type='CELERY',
                    actor_id=None,
                    reason='Payment timeout',
                    justification='Automatic expiry by system'
                )
                
                # Create timeline event
                from kiboss.apps.bookings.models import BookingTimeline
                BookingTimeline.log_event(
                    booking=booking,
                    event_type='EXPIRED',
                    description='Booking expired due to payment timeout',
                    actor_type='SYSTEM'
                )
                
                # Send notifications
                NotificationService.send_booking_expired_notification(booking)
                
                # Update asset statistics
                booking.asset.total_bookings -= 1
                booking.asset.save(update_fields=['total_bookings'])
                
                expired_count += 1
                logger.info(f"Expired booking {booking.id}")
                
        except Exception as e:
            logger.error(f"Failed to expire booking {booking.id}: {e}")
            raise self.retry(exc=e)
    
    logger.info(f"Expired {expired_count} pending bookings")
    return {'expired_count': expired_count}
```

### 2.2 Check Active Bookings

```python
@shared_task(bind=True)
def check_active_bookings(self):
    """
    Monitor active bookings and detect late returns.
    
    Schedule: Every 5 minutes
    
    Process:
    1. Find all ACTIVE bookings where end_time has passed
    2. Check for late returns
    3. Calculate late fees if applicable
    4. Send reminders and notifications
    """
    from kiboss.apps.bookings.models import Booking, BookingStatus
    from kiboss.apps.notifications.services import NotificationService
    
    late_bookings = Booking.objects.filter(
        status=BookingStatus.ACTIVE,
        end_time__lt=timezone.now()
    ).select_related('asset', 'renter')
    
    late_count = 0
    
    for booking in late_bookings:
        # Calculate late minutes
        late_minutes = int((timezone.now() - booking.end_time).total_seconds() / 60)
        
        if late_minutes > booking.grace_period_minutes:
            booking.is_late = True
            booking.late_minutes = late_minutes - booking.grace_period_minutes
            
            # Calculate late fee
            late_fee = booking.calculate_late_fee(timezone.now())
            booking.late_fee_charged = late_fee
            
            booking.save()
            
            # Send notification
            NotificationService.send_late_return_notification(
                booking, late_minutes, late_fee
            )
            
            late_count += 1
    
    if late_count > 0:
        logger.warning(f"Detected {late_count} late bookings")
    
    return {'late_count': late_count}
```

### 2.3 Process Completed Bookings

```python
@shared_task(bind=True)
def process_completed_bookings(self):
    """
    Process completed bookings and release payments.
    
    Schedule: Every 5 minutes
    
    Process:
    1. Find all COMPLETED bookings awaiting payment release
    2. Calculate final amounts (including late fees)
    3. Release escrow to asset owner
    4. Enable ratings
    5. Send completion notifications
    """
    from kiboss.apps.bookings.models import Booking, BookingStatus
    from kiboss.apps.payments.models import Payment, PaymentStatus
    from kiboss.apps.notifications.services import NotificationService
    from kiboss.apps.ratings.services import RatingService
    
    completed_bookings = Booking.objects.filter(
        status=BookingStatus.COMPLETED,
        payment__status=PaymentStatus.ESCROW,
        payment__escrow_held_at__isnull=False
    ).select_related(
        'payment', 'asset', 'asset__owner', 'renter'
    )
    
    for booking in completed_bookings:
        try:
            payment = booking.payment
            
            # Calculate final amount
            final_amount = payment.escrow_amount
            if booking.late_fee_charged and booking.late_fee_charged > 0:
                final_amount -= booking.late_fee_charged
                payment.penalty_amount = booking.late_fee_charged
                payment.penalty_reason = 'Late return fee'
            
            # Release escrow
            payment.release_from_escrow(
                release_amount=final_amount,
                deduct_fees=payment.amount - final_amount
            )
            
            # Update booking
            booking.payment = payment
            booking.save()
            
            # Enable ratings
            RatingService.enable_booking_ratings(booking.id)
            
            # Send notifications
            NotificationService.send_booking_completed_notification(booking)
            
            # Update owner earnings
            booking.asset.owner.trust_score  # Recalculate if needed
            
            logger.info(f"Processed completed booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Failed to process booking {booking.id}: {e}")
    
    return {'processed_count': completed_bookings.count()}
```

### 2.4 Check No-Shows

```python
@shared_task(bind=True)
def check_no_shows(self):
    """
    Detect and process no-show bookings.
    
    Schedule: Every 1 minute
    
    Process:
    1. Find CONFIRMED bookings past their start time with no activity
    2. Mark as no-show
    3. Apply no-show penalties
    4. Update trust scores
    5. Release availability for standby
    """
    from kiboss.apps.bookings.models import Booking, BookingStatus
    from kiboss.apps.notifications.services import NotificationService
    
    no_show_bookings = Booking.objects.filter(
        status=BookingStatus.CONFIRMED,
        start_time__lt=timezone.now()
    ).filter(
        # No check-in or activity recorded
        created_at__lt=timezone.now() - timedelta(hours=1)
    ).select_related('asset', 'renter')
    
    for booking in no_show_bookings:
        # Mark as no-show
        booking.transition_to(
            BookingStatus.EXPIRED,
            actor_type='CELERY',
            actor_id=None,
            reason='No-show',
            justification='User did not show up for booking'
        )
        
        # Apply no-show penalty if configured
        if booking.asset.get_property('no_show_penalty'):
            from kiboss.apps.payments.models import Payment, PaymentStatus
            payment = booking.payment
            
            if payment and payment.status == PaymentStatus.ESCROW:
                penalty = booking.total_price * Decimal('0.25')  # 25% penalty
                payment.apply_penalty(penalty, reason='No-show penalty')
        
        # Update trust score
        from kiboss.apps.users.models import TrustScore
        trust, _ = TrustScore.objects.get_or_create(user=booking.renter)
        trust.no_shows += 1
        trust.calculate_overall_score()
        
        # Send notification
        NotificationService.send_no_show_notification(booking)
        
        logger.info(f"Marked booking {booking.id} as no-show")
    
    return {'no_show_count': no_show_bookings.count()}
```

---

## 3. Ride Tasks

### 3.1 Generate Scheduled Rides

```python
# kiboss/apps/rides/tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_scheduled_rides(self):
    """
    Generate ride instances from recurring schedules.
    
    Schedule: Every hour
    
    Process:
    1. Find all active ride schedules
    2. Generate rides for the next 30 days
    3. Avoid duplicate rides
    """
    from kiboss.apps.rides.models import RideSchedule, Ride
    
    schedules = RideSchedule.objects.filter(
        is_active=True
    ).filter(
        models.Q(valid_until__isnull=True) |
        models.Q(valid_until__gt=timezone.now().date())
    )
    
    total_created = 0
    
    for schedule in schedules:
        try:
            rides = schedule.generate_rides(days_ahead=30)
            total_created += len(rides)
            logger.info(f"Generated {len(rides)} rides from schedule {schedule.id}")
        except Exception as e:
            logger.error(f"Failed to generate rides for schedule {schedule.id}: {e}")
    
    return {'schedules_processed': schedules.count(), 'rides_created': total_created}
```

### 3.2 Process Ride Departures

```python
@shared_task(bind=True)
def process_ride_departures(self):
    """
    Process ride departures and detect no-shows.
    
    Schedule: Every 1 minute
    
    Process:
    1. Find rides that have departed
    2. Check for no-show passengers
    3. Update ride status
    4. Notify drivers of passenger status
    """
    from kiboss.apps.rides.models import Ride, RideStatus, SeatBooking, SeatBookingStatus
    from kiboss.apps.notifications.services import NotificationService
    
    departed_rides = Ride.objects.filter(
        status=RideStatus.DEPARTED,
        departure_time__lt=timezone.now()
    )
    
    for ride in departed_rides:
        # Check for no-show passengers
        no_shows = SeatBooking.objects.filter(
            ride=ride,
            status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED],
            checked_in_at__isnull=True
        )
        
        for seat_booking in no_shows:
            seat_booking.mark_no_show()
            
            # Apply penalty
            if ride.no_show_cutoff_minutes:
                seat_booking.no_show_penalty_applied = True
        
        # Update ride status
        ride.status = RideStatus.IN_TRANSIT
        ride.save()
        
        # Notify driver
        NotificationService.send_ride_departed_notification(ride)
        
        logger.info(f"Processed departure for ride {ride.id}")
    
    return {'rides_processed': departed_rides.count()}
```

---

## 4. Notification Tasks

### 4.1 Send Pending Notifications

```python
# kiboss/apps/notifications/tasks.py

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_pending_notifications(self):
    """
    Send pending notifications through configured channels.
    
    Schedule: Every 30 seconds
    
    Process:
    1. Find pending notifications
    2. Filter by user preferences and quiet hours
    3. Send through each channel (in-app, email, push)
    4. Update delivery status
    5. Handle failures and retries
    """
    from kiboss.apps.notifications.models import Notification, NotificationStatus, NotificationChannel
    from kiboss.apps.notifications.services import EmailNotificationService, PushNotificationService
    
    pending = Notification.objects.filter(
        status=NotificationStatus.PENDING,
        created_at__gt=timezone.now() - timedelta(hours=24)  # Only recent notifications
    ).order_by('priority', 'created_at')[:100]  # Process in batches
    
    sent_count = 0
    failed_count = 0
    
    for notification in pending:
        try:
            # Check user preferences
            if not notification.user.notification_preferences:
                continue
            
            # Get channels to send
            channels = notification.channels or [NotificationChannel.IN_APP]
            
            # Send through each channel
            for channel in channels:
                if channel == NotificationChannel.IN_APP:
                    # Mark as sent for in-app
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = timezone.now()
                    notification.save()
                    sent_count += 1
                    
                elif channel == NotificationChannel.EMAIL:
                    EmailNotificationService.send(notification)
                    
                elif channel == NotificationChannel.PUSH:
                    PushNotificationService.send(notification)
            
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}")
            notification.retry_count += 1
            notification.failure_reason = str(e)
            
            if notification.retry_count >= 3:
                notification.status = NotificationStatus.FAILED
            
            notification.save()
            failed_count += 1
    
    return {'sent': sent_count, 'failed': failed_count}
```

### 4.2 Send Reminder Notifications

```python
@shared_task(bind=True)
def send_reminder_notifications(self):
    """
    Send booking reminders.
    
    Schedule: Every 15 minutes
    
    Process:
    1. Find upcoming bookings (within 24 hours)
    2. Send reminders to renters and owners
    3. Avoid duplicate reminders
    """
    from kiboss.apps.notifications.models import Notification
    from kiboss.apps.bookings.models import Booking, BookingStatus
    from kiboss.apps.notifications.services import NotificationService
    from datetime import timedelta
    
    # Upcoming bookings
    upcoming = Booking.objects.filter(
        status=BookingStatus.CONFIRMED,
        start_time__range=[
            timezone.now() + timedelta(hours=1),
            timezone.now() + timedelta(hours=24)
        ]
    ).exclude(
        # Exclude if reminder already sent
        notifications__notification_type='booking_reminder'
    ).select_related('asset', 'renter')
    
    for booking in upcoming:
        # Send reminder
        NotificationService.send_booking_reminder_notification(booking)
        logger.info(f"Sent reminder for booking {booking.id}")
    
    return {'reminders_sent': upcoming.count()}
```

---

## 5. Rating Tasks

### 5.1 Reveal Mutual Ratings

```python
# kiboss/apps/ratings/tasks.py

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def reveal_mutual_ratings(self):
    """
    Reveal ratings when both parties have submitted.
    
    Schedule: Every 5 minutes
    
    Process:
    1. Find ratings that are mutually submitted but not revealed
    2. Reveal ratings to both parties
    3. Update user trust scores
    4. Send notifications
    """
    from kiboss.apps.ratings.models import Rating, RatingStatus
    from kiboss.apps.notifications.services import NotificationService
    
    # Find pending mutual reveals
    pending_ratings = Rating.objects.filter(
        status=RatingStatus.SUBMITTED,
        is_mutually_revealed=False
    ).select_related('booking', 'reviewer', 'reviewee')
    
    revealed_count = 0
    
    for rating in pending_ratings:
        # Check if there's a matching rating from the other party
        matching = Rating.objects.filter(
            booking=rating.booking,
            reviewer=rating.reviewee,
            reviewee=rating.reviewer,
            status=RatingStatus.SUBMITTED
        ).first()
        
        if matching:
            # Reveal both ratings
            rating.reveal_mutual()
            matching.reveal_mutual()
            
            # Update trust scores
            from kiboss.apps.users.models import TrustScore
            
            reviewer_trust, _ = TrustScore.objects.get_or_create(
                user=rating.reviewer
            )
            reviewer_trust.update_from_rating('reliability', rating.overall_rating)
            
            reviewee_trust, _ = TrustScore.objects.get_or_create(
                user=rating.reviewee
            )
            reviewee_trust.update_from_rating('reliability', matching.overall_rating)
            
            # Send notifications
            NotificationService.send_rating_revealed_notification(rating)
            NotificationService.send_rating_revealed_notification(matching)
            
            revealed_count += 1
    
    return {'revealed_count': revealed_count}
```

---

## 6. Cleanup Tasks

### 6.1 Cleanup Expired Locks

```python
# kiboss/apps/common/tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def cleanup_expired_locks(self):
    """
    Cleanup expired database locks.
    
    Schedule: Every hour
    
    Process:
    1. Find all expired BookingLock records
    2. Delete them
    3. Log cleanup statistics
    """
    from kiboss.apps.bookings.models import BookingLock
    
    expired = BookingLock.objects.filter(
        expires_at__lt=timezone.now()
    )
    
    count = expired.count()
    expired.delete()
    
    if count > 0:
        logger.info(f"Cleaned up {count} expired locks")
    
    return {'cleaned_locks': count}
```

### 6.2 Cleanup Old Notifications

```python
@shared_task(bind=True)
def cleanup_old_notifications(self):
    """
    Cleanup old read notifications.
    
    Schedule: Daily
    
    Process:
    1. Find read notifications older than 30 days
    2. Delete them (keep un/read for 30 days)
    """
    from kiboss.apps.notifications.models import Notification, NotificationStatus
    from datetime import timedelta
    
    old = Notification.objects.filter(
        status=NotificationStatus.READ,
        read_at__lt=timezone.now() - timedelta(days=30)
    )
    
    count = old.count()
    old.delete()
    
    logger.info(f"Cleaned up {count} old notifications")
    
    return {'cleaned_notifications': count}
```

---

## 7. Task Error Handling

### 7.1 Retry Configuration

```python
# Global retry configuration for tasks

TASK_RETRY_CONFIG = {
    'expire_pending_bookings': {
        'max_retries': 3,
        'default_retry_delay': 60,
        'autoretry_for': (Exception,),
        'retry_backoff': True,
    },
    'send_pending_notifications': {
        'max_retries': 5,
        'default_retry_delay': 30,
        'autoretry_for': (ConnectionError, TimeoutError),
        'retry_backoff': True,
    },
}
```

### 7.2 Task Monitoring

```python
# Task health check

@shared_task
def task_health_check():
    """
    Check Celery task health.
    
    Returns:
        dict: Health status of various task queues
    """
    from kiboss.celery import app
    
    inspect = app.control.inspect()
    
    return {
        'registered': inspect.registered(),
        'active': inspect.active(),
        'scheduled': inspect.scheduled(),
        'stats': inspect.stats(),
    }
```

---

## 8. Performance Considerations

### 8.1 Task Optimization

1. **Batch Processing**: Process records in batches (100-500 per task)
2. **Select Related**: Use `select_related()` and `prefetch_related()` to minimize queries
3. **Index Awareness**: Ensure database indexes support common query patterns
4. **Memory Management**: Use generators for large datasets
5. **Timeout Limits**: Set appropriate time limits for long-running tasks

### 8.2 Queue Configuration

```python
# Separate queues for different task types

app.conf.task_queues = (
    Queue('default', routing_key='default'),
    Queue('bookings', routing_key='bookings'),
    Queue('rides', routing_key='rides'),
    Queue('notifications', routing_key='notifications'),
    Queue('cleanups', routing_key='cleanups'),
)

# Route tasks to appropriate queues
app.conf.task_routes = {
    'bookings.tasks.*': {'queue': 'bookings'},
    'rides.tasks.*': {'queue': 'rides'},
    'notifications.tasks.*': {'queue': 'notifications'},
    'common.tasks.cleanup*': {'queue': 'cleanups'},
}
```

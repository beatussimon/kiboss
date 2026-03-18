"""
Celery Tasks for KIBOSS Booking Engine

Implements background tasks for:
- Booking expiry
- Booking reminders
- Late return detection
- Payment timeout handling
- Contract expiration
"""

import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from kiboss.apps.bookings.models import Booking, BookingStatus
from kiboss.apps.payments.models import Payment, PaymentStatus
from kiboss.apps.notifications.models import Notification, NotificationCategory
from kiboss.apps.contracts.models import Contract, ContractStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_pending_bookings(self):
    """
    Expired pending bookings that haven't been paid within timeout period.
    
    Scheduled to run every 5 minutes.
    """
    from kiboss.apps.common.locking import lock_manager
    
    # Acquire lock to prevent concurrent execution
    lock_key = "lock:task:expire_pending_bookings"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=300, max_retries=1)
    
    if not lock_token:
        logger.info("Another worker is processing pending booking expiry")
        return
    
    try:
        from django.contrib.contenttypes.models import ContentType
        from kiboss.apps.payments.models import ManualPaymentReceipt
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus

        # Find pending bookings older than 15 minutes
        timeout = timezone.now() - timedelta(minutes=15)
        
        expired_bookings = Booking.objects.filter(
            status=BookingStatus.PENDING,
            created_at__lt=timeout
        )

        expired_ride_bookings = SeatBooking.objects.filter(
            status=SeatBookingStatus.RESERVED,
            created_at__lt=timeout
        )
        
        asset_ctype = ContentType.objects.get_for_model(Booking)
        ride_ctype = ContentType.objects.get_for_model(SeatBooking)

        count = 0
        for booking in expired_bookings:
            if ManualPaymentReceipt.objects.filter(
                content_type=asset_ctype,
                object_id=booking.id,
                status__in=['PENDING', 'APPROVED']
            ).exists():
                continue

            try:
                with transaction.atomic():
                    # Transition to expired
                    booking.transition_to(
                        BookingStatus.EXPIRED,
                        actor_type='CELERY',
                        actor_id=None,
                        reason='Payment timeout'
                    )
                    
                    # Cancel payment if exists
                    if booking.payment:
                        payment = booking.payment
                        payment.status = PaymentStatus.FAILED
                        payment.failure_code = 'TIMEOUT'
                        payment.failure_message = 'Payment not received within timeout'
                        payment.save()
                    
                    # Notify parties
                    create_notification(
                        booking.renter,
                        NotificationCategory.BOOKING,
                        'Booking Expired',
                        f'Your booking for {booking.asset.name} has expired due to payment timeout.',
                        booking=booking
                    )
                    
                    create_notification(
                        booking.asset.owner,
                        NotificationCategory.BOOKING,
                        'Booking Expired',
                        f'A pending booking for {booking.asset.name} has expired.',
                        booking=booking
                    )
                    
                    count += 1
                    logger.info(f"Expired booking {booking.id}")
                    
            except Exception as e:
                logger.error(f"Error expiring booking {booking.id}: {e}")

        for seat_booking in expired_ride_bookings:
            if ManualPaymentReceipt.objects.filter(
                content_type=ride_ctype,
                object_id=seat_booking.id,
                status__in=['PENDING', 'APPROVED']
            ).exists():
                continue

            try:
                with transaction.atomic():
                    seat_booking.cancel(reason='Payment timeout')
                    
                    if seat_booking.payment:
                        payment = seat_booking.payment
                        payment.status = PaymentStatus.FAILED
                        payment.failure_code = 'TIMEOUT'
                        payment.failure_message = 'Payment not received within timeout'
                        payment.save()
                    
                    create_notification(
                        seat_booking.passenger,
                        NotificationCategory.BOOKING,
                        'Ride Booking Expired',
                        f'Your ride booking for seat {seat_booking.seat_number} on {seat_booking.ride.origin} to {seat_booking.ride.destination} has expired due to payment timeout.',
                        ride=seat_booking.ride
                    )
                    
                    count += 1
                    logger.info(f"Expired seat booking {seat_booking.id}")
                    
            except Exception as e:
                logger.error(f"Error expiring seat booking {seat_booking.id}: {e}")
        
        logger.info(f"Expired {count} pending bookings")
        return {'expired': count}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_confirmed_no_shows(self):
    """
    Mark confirmed bookings as expired if no-show (past start time + grace period).
    
    Scheduled to run every 5 minutes.
    """
    from kiboss.apps.common.locking import lock_manager
    
    lock_key = "lock:task:expire_no_shows"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=300, max_retries=1)
    
    if not lock_token:
        logger.info("Another worker is processing no-shows")
        return
    
    try:
        # Find confirmed bookings that should have started
        no_show_cutoff = timezone.now()
        
        # Check for bookings that are past their start time
        expired_bookings = Booking.objects.filter(
            status=BookingStatus.CONFIRMED,
            start_time__lt=no_show_cutoff
        )
        
        count = 0
        for booking in expired_bookings:
            try:
                with transaction.atomic():
                    # Apply grace period check
                    grace_end = booking.start_time + timedelta(
                        minutes=booking.grace_period_minutes
                    )
                    
                    if timezone.now() > grace_end:
                        booking.transition_to(
                            BookingStatus.EXPIRED,
                            actor_type='CELERY',
                            actor_id=None,
                            reason='No-show - user did not start rental'
                        )
                        
                        # Handle payment (partial refund logic would go here)
                        if booking.payment:
                            payment = booking.payment
                            # Apply no-show penalty
                            payment.apply_penalty(
                                payment.amount * 0.25,  # 25% no-show penalty
                                'No-show penalty'
                            )
                        
                        # Notify parties
                        create_notification(
                            booking.renter,
                            NotificationCategory.BOOKING,
                            'Booking Expired - No Show',
                            f'Your booking for {booking.asset.name} has been marked as no-show.',
                            booking=booking
                        )
                        
                        count += 1
                        logger.info(f"Marked booking {booking.id} as no-show expired")
                        
            except Exception as e:
                logger.error(f"Error processing no-show for booking {booking.id}: {e}")
        
        logger.info(f"Processed {count} no-show bookings")
        return {'no_shows': count}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_booking_completion(self):
    """
    Check and complete active bookings that have reached their end time.
    
    Scheduled to run every 5 minutes.
    """
    from kiboss.apps.common.locking import lock_manager
    
    lock_key = "lock:task:check_completion"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=300, max_retries=1)
    
    if not lock_token:
        logger.info("Another worker is processing completions")
        return
    
    try:
        # Find active bookings past their end time
        completed_bookings = Booking.objects.filter(
            status=BookingStatus.ACTIVE,
            end_time__lt=timezone.now()
        )
        
        count = 0
        for booking in completed_bookings:
            try:
                with transaction.atomic():
                    booking.transition_to(
                        BookingStatus.COMPLETED,
                        actor_type='CELERY',
                        actor_id=None,
                        reason='Booking period ended'
                    )
                    booking.completed_at = timezone.now()
                    booking.save()
                    
                    # Release escrow to owner
                    if booking.payment and booking.payment.status == PaymentStatus.ESCROW:
                        booking.payment.release_from_escrow()
                    
                    # Notify parties
                    create_notification(
                        booking.renter,
                        NotificationCategory.BOOKING,
                        'Booking Completed',
                        f'Your booking for {booking.asset.name} has been completed.',
                        booking=booking
                    )
                    
                    create_notification(
                        booking.asset.owner,
                        NotificationCategory.BOOKING,
                        'Booking Completed',
                        f'The rental for {booking.asset.name} has been completed.',
                        booking=booking
                    )
                    
                    count += 1
                    logger.info(f"Completed booking {booking.id}")
                    
            except Exception as e:
                logger.error(f"Error completing booking {booking.id}: {e}")
        
        logger.info(f"Completed {count} bookings")
        return {'completed': count}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_reminders(self):
    """
    Send reminders for upcoming bookings.
    
    Scheduled to run every hour.
    """
    from kiboss.apps.common.locking import lock_manager
    
    lock_key = "lock:task:send_reminders"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=3600, max_retries=1)
    
    if not lock_token:
        logger.info("Another worker is sending reminders")
        return
    
    try:
        # Send reminders 24 hours before
        reminder_time = timezone.now() + timedelta(hours=24)
        window_end = reminder_time + timedelta(minutes=30)
        
        upcoming = Booking.objects.filter(
            status=BookingStatus.CONFIRMED,
            start_time__gte=reminder_time,
            start_time__lt=window_end
        )
        
        count = 0
        for booking in upcoming:
            try:
                create_notification(
                    booking.renter,
                    NotificationCategory.BOOKING,
                    'Booking Reminder',
                    f'Reminder: Your booking for {booking.asset.name} starts tomorrow at {booking.start_time.strftime("%H:%M")}.',
                    booking=booking
                )
                
                create_notification(
                    booking.asset.owner,
                    NotificationCategory.BOOKING,
                    'Booking Reminder',
                    f'Reminder: {booking.renter.email} has a booking for {booking.asset.name} starting tomorrow.',
                    booking=booking
                )
                
                count += 1
                
            except Exception as e:
                logger.error(f"Error sending reminder for booking {booking.id}: {e}")
        
        logger.info(f"Sent reminders for {count} bookings")
        return {'reminders': count}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_late_returns(self):
    """
    Check for late returns on completed bookings.
    
    Scheduled to run every 15 minutes.
    """
    from kiboss.apps.common.locking import lock_manager
    
    lock_key = "lock:task:late_returns"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=900, max_retries=1)
    
    if not lock_token:
        logger.info("Another worker is processing late returns")
        return
    
    try:
        # Find active bookings past their end time + grace period
        late_cutoff = timezone.now()
        
        late_bookings = Booking.objects.filter(
            status=BookingStatus.ACTIVE,
            end_time__lt=late_cutoff
        )
        
        count = 0
        for booking in late_bookings:
            try:
                with transaction.atomic():
                    # Calculate late duration
                    return_time = timezone.now()
                    late_minutes = int((return_time - booking.end_time).total_seconds() / 60)
                    
                    # Mark as late
                    booking.is_late = True
                    booking.late_minutes = late_minutes
                    
                    # Calculate late fee
                    late_fee = booking.calculate_late_fee(return_time)
                    booking.late_fee_charged = late_fee
                    
                    # Apply penalty to payment
                    if booking.payment and late_fee > 0:
                        booking.payment.apply_penalty(
                            late_fee,
                            f'Late return - {late_minutes} minutes'
                        )
                    
                    booking.save()
                    
                    # Notify parties
                    create_notification(
                        booking.renter,
                        NotificationCategory.PAYMENT,
                        'Late Return Fee Applied',
                        f'A late return fee of {late_fee} has been applied to your booking.',
                        booking=booking
                    )
                    
                    create_notification(
                        booking.asset.owner,
                        NotificationCategory.PAYMENT,
                        'Late Return Reported',
                        f'The rental for {booking.asset.name} was returned {late_minutes} minutes late.',
                        booking=booking
                    )
                    
                    count += 1
                    logger.info(f"Processed late return for booking {booking.id}: {late_minutes} minutes, fee: {late_fee}")
                    
            except Exception as e:
                logger.error(f"Error processing late return for booking {booking.id}: {e}")
        
        logger.info(f"Processed {count} late returns")
        return {'late_returns': count}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


@shared_task(bind=True)
def cleanup_old_notifications(self):
    """
    Clean up old read notifications (older than 30 days).
    
    Scheduled to run daily.
    """
    from kiboss.apps.common.locking import lock_manager
    
    lock_key = "lock:task:cleanup_notifications"
    lock_token = lock_manager.acquire_lock(lock_key, ttl=86400, max_retries=1)
    
    if not lock_token:
        return
    
    try:
        cutoff = timezone.now() - timedelta(days=30)
        
        deleted = Notification.objects.filter(
            status='READ',
            read_at__lt=cutoff
        ).delete()
        
        logger.info(f"Cleaned up {deleted[0]} old notifications")
        return {'deleted': deleted[0]}
        
    finally:
        lock_manager.release_lock(lock_key, lock_token)


def create_notification(user, category, title, message, booking=None, ride=None):
    """
    Helper function to create a notification.
    """
    notification = Notification.objects.create(
        user=user,
        category=category,
        notification_type='system',
        title=title,
        message=message,
        status='PENDING',
        channels=['in_app'],
        booking=booking,
        ride=ride
    )
    return notification

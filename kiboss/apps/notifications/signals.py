"""
Notification Signals for KIBOSS

Automatically triggers notifications on model events.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# Booking Signals
@receiver(post_save, sender='bookings.Booking')
def booking_notification_handler(sender, instance, created, **kwargs):
    """Handle booking-related notifications."""
    from .services import NotificationService
    
    if created:
        # New booking created
        NotificationService.notify_booking_created(instance)
    else:
        # Check for status changes
        if hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status
            current_status = instance.status
            
            if previous_status != current_status:
                if current_status == 'CONFIRMED':
                    NotificationService.notify_booking_confirmed(instance)
                elif current_status == 'CANCELLED':
                    # Get cancellation info from the model
                    cancelled_by = instance.cancelled_by
                    reason = instance.cancellation_reason or ''
                    NotificationService.notify_booking_cancelled(instance, cancelled_by, reason)
                elif current_status == 'COMPLETED':
                    NotificationService.notify_booking_completed(instance)


# Ride Signals
@receiver(post_save, sender='rides.Ride')
def ride_notification_handler(sender, instance, created, **kwargs):
    """Handle ride-related notifications."""
    from .services import NotificationService
    
    if created:
        NotificationService.notify_ride_created(instance)
    else:
        # Check for status changes
        if hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status
            current_status = instance.status
            
            if previous_status != current_status and current_status == 'CANCELLED':
                NotificationService.notify_ride_cancelled(instance, instance.driver)


# Seat Booking Signals
@receiver(post_save, sender='rides.SeatBooking')
def seat_booking_notification_handler(sender, instance, created, **kwargs):
    """Handle seat booking notifications."""
    from .services import NotificationService
    
    if created:
        NotificationService.notify_ride_booked(instance.ride, instance)


# Payment Signals
@receiver(post_save, sender='payments.Payment')
def payment_notification_handler(sender, instance, created, **kwargs):
    """Handle payment-related notifications."""
    from .services import NotificationService
    
    if not created:
        # Check for status changes
        if hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status
            current_status = instance.status
            
            if previous_status != current_status:
                if current_status == 'ESCROW':
                    # Payment is being held
                    NotificationService.notify_payment_received(instance)
                elif current_status == 'REFUNDED':
                    # Payment was refunded
                    NotificationService.notify_payment_refunded(instance, instance.refunded_amount)


# Message Signals
@receiver(post_save, sender='messaging.Message')
def message_notification_handler(sender, instance, created, **kwargs):
    """Handle message notifications."""
    from .services import NotificationService
    
    if created and not instance.is_deleted:
        NotificationService.notify_message_received(instance)


# Rating Signals
@receiver(post_save, sender='ratings.Rating')
def rating_notification_handler(sender, instance, created, **kwargs):
    """Handle rating notifications."""
    from .services import NotificationService
    
    if created:
        NotificationService.notify_rating_received(instance)


# Dispute Signals
@receiver(post_save, sender='payments.Dispute')
def dispute_notification_handler(sender, instance, created, **kwargs):
    """Handle dispute notifications."""
    from .services import NotificationService
    
    if created:
        NotificationService.notify_dispute_created(instance)
    else:
        # Check for resolution
        if hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status
            current_status = instance.status
            
            if previous_status != current_status and current_status == 'RESOLVED':
                NotificationService.notify_dispute_resolved(instance, instance.resolution or '')


# Helper to track previous status
def track_previous_status(sender, instance, **kwargs):
    """Track previous status for comparison in post_save."""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._previous_status = getattr(old_instance, 'status', None)
        except sender.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


# Register pre_save signals for status tracking
from django.db.models.signals import pre_save

pre_save.connect(track_previous_status, sender='bookings.Booking')
pre_save.connect(track_previous_status, sender='rides.Ride')
pre_save.connect(track_previous_status, sender='payments.Payment')
pre_save.connect(track_previous_status, sender='payments.Dispute')

"""
Notification Services for KIBOSS - Event-Driven Notifications

This module provides a unified interface for creating and sending notifications
across all system events including bookings, rides, payments, messages, etc.
"""

import logging
from django.utils import timezone
from django.db import transaction
from celery import shared_task
from .models import (
    Notification, NotificationCategory, NotificationStatus, NotificationChannel,
    NotificationPreference
)
from .push_service import PushNotificationService
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def send_notification_task(
    user_id,
    category,
    notification_type,
    title,
    message,
    action_url='',
    booking_id=None,
    ride_id=None,
    priority=0,
    channels=None,
    data=None
):
    """Celery task to create and send notification."""
    from kiboss.apps.users.models import User
    from kiboss.apps.bookings.models import Booking
    from kiboss.apps.rides.models import Ride

    try:
        user = User.objects.get(id=user_id)
        booking = Booking.objects.get(id=booking_id) if booking_id else None
        ride = Ride.objects.get(id=ride_id) if ride_id else None

        if channels is None:
            channels = [NotificationChannel.IN_APP]

        notification = Notification.objects.create(
            user=user,
            category=category,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            booking=booking,
            ride=ride,
            priority=priority,
            channels=channels,
            status=NotificationStatus.SENT,
            sent_at=timezone.now(),
            data=data or {}
        )
        logger.info(f"Async notification {notification.id} created for user {user.id}")

        # Deliver to other channels
        if NotificationChannel.PUSH in channels:
            PushNotificationService.send(user, title, message, data=data)
        
        if NotificationChannel.EMAIL in channels:
            # T5-08: Email Notification wiring
            try:
                template_name = f"email/{notification_type.lower()}.html"
                context = {
                    'user': user,
                    'title': title,
                    'message': message,
                    'action_url': action_url,
                    'booking': booking,
                    'ride': ride,
                    'data': data or {}
                }
                html_message = render_to_string(template_name, context)
                send_mail(
                    subject=title,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=True
                )
            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")

        return str(notification.id)
    except Exception as e:
        logger.error(f"Failed async notification for user {user_id}: {e}")
        return None


class NotificationService:
    """
    Central service for creating and managing notifications.
    
    All notifications should be created through this service to ensure
    consistency and proper event tracking.
    """
    
    @staticmethod
    def create_notification(
        user,
        category,
        notification_type,
        title,
        message,
        action_url='',
        booking=None,
        ride=None,
        priority=0,
        channels=None,
        data=None
    ):
        """
        Create a new notification for a user (Asynchronously).
        """
        send_notification_task.delay(
            user_id=user.id,
            category=category,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            booking_id=booking.id if booking else None,
            ride_id=ride.id if ride else None,
            priority=priority,
            channels=channels,
            data=data
        )
        return None
    
    @staticmethod
    def notify_booking_created(booking):
        """Notify owner about new booking request."""
        # Notify asset owner
        NotificationService.create_notification(
            user=booking.asset.owner,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_CREATED',
            title='New Booking Request',
            message=f'{booking.renter.get_full_name()} wants to book {booking.asset.name}',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=10
        )
        
        # Notify renter (confirmation)
        NotificationService.create_notification(
            user=booking.renter,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_REQUEST_SENT',
            title='Booking Request Sent',
            message=f'Your booking request for {booking.asset.name} has been sent',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=5
        )
    
    @staticmethod
    def notify_booking_confirmed(booking):
        """Notify renter that booking is confirmed."""
        NotificationService.create_notification(
            user=booking.renter,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_CONFIRMED',
            title='Booking Confirmed',
            message=f'Your booking for {booking.asset.name} has been confirmed',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=15
        )
    
    @staticmethod
    def notify_booking_cancelled(booking, cancelled_by, reason=''):
        """Notify relevant parties about booking cancellation."""
        # Determine who to notify
        if cancelled_by == booking.renter:
            # Renter cancelled - notify owner
            NotificationService.create_notification(
                user=booking.asset.owner,
                category=NotificationCategory.BOOKING,
                notification_type='BOOKING_CANCELLED',
                title='Booking Cancelled',
                message=f'Booking for {booking.asset.name} has been cancelled by the renter',
                action_url=f'/bookings/{booking.id}',
                booking=booking,
                priority=10
            )
        else:
            # Owner cancelled - notify renter
            NotificationService.create_notification(
                user=booking.renter,
                category=NotificationCategory.BOOKING,
                notification_type='BOOKING_CANCELLED',
                title='Booking Cancelled',
                message=f'Your booking for {booking.asset.name} has been cancelled by the owner',
                action_url=f'/bookings/{booking.id}',
                booking=booking,
                priority=15
            )
    
    @staticmethod
    def notify_booking_completed(booking):
        """Notify both parties about booking completion."""
        # Notify renter
        NotificationService.create_notification(
            user=booking.renter,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_COMPLETED',
            title='Booking Completed',
            message=f'Your booking for {booking.asset.name} has been completed. Please leave a review!',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=10
        )
        
        # Notify owner
        NotificationService.create_notification(
            user=booking.asset.owner,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_COMPLETED',
            title='Booking Completed',
            message=f'Booking for {booking.asset.name} has been completed. Please leave a review!',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=10
        )
    
    @staticmethod
    def notify_booking_starting_soon(booking, hours_before=24):
        """Notify renter about upcoming booking."""
        NotificationService.create_notification(
            user=booking.renter,
            category=NotificationCategory.BOOKING,
            notification_type='BOOKING_REMINDER',
            title='Booking Starting Soon',
            message=f'Your booking for {booking.asset.name} starts in {hours_before} hours',
            action_url=f'/bookings/{booking.id}',
            booking=booking,
            priority=15
        )
    
    @staticmethod
    def notify_ride_created(ride):
        """Notify about new ride creation (for driver confirmation)."""
        NotificationService.create_notification(
            user=ride.driver,
            category=NotificationCategory.RIDE,
            notification_type='RIDE_CREATED',
            title='Ride Created',
            message=f'Your ride from {ride.origin} to {ride.destination} has been created',
            action_url=f'/rides/{ride.id}',
            ride=ride,
            priority=5
        )
    
    @staticmethod
    def notify_ride_booked(ride, seat_booking):
        """Notify driver about new passenger."""
        NotificationService.create_notification(
            user=ride.driver,
            category=NotificationCategory.RIDE,
            notification_type='RIDE_NEW_PASSENGER',
            title='New Passenger',
            message=f'{seat_booking.passenger.get_full_name()} booked seat {seat_booking.seat_number} on your ride',
            action_url=f'/rides/{ride.id}',
            ride=ride,
            priority=10
        )
        
        # Notify passenger (confirmation)
        NotificationService.create_notification(
            user=seat_booking.passenger,
            category=NotificationCategory.RIDE,
            notification_type='RIDE_BOOKED',
            title='Ride Booked',
            message=f'You booked seat {seat_booking.seat_number} on ride from {ride.origin} to {ride.destination}',
            action_url=f'/rides/{ride.id}',
            ride=ride,
            priority=10
        )
    
    @staticmethod
    def notify_ride_cancelled(ride, cancelled_by):
        """Notify passengers about ride cancellation."""
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        
        # Notify all passengers
        passengers = SeatBooking.objects.filter(
            ride=ride,
            status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
        ).select_related('passenger')
        
        for seat_booking in passengers:
            NotificationService.create_notification(
                user=seat_booking.passenger,
                category=NotificationCategory.RIDE,
                notification_type='RIDE_CANCELLED',
                title='Ride Cancelled',
                message=f'Your ride from {ride.origin} to {ride.destination} has been cancelled by the driver',
                action_url=f'/rides/{ride.id}',
                ride=ride,
                priority=15
            )
    
    @staticmethod
    def notify_ride_departing_soon(ride, hours_before=1):
        """Notify driver and passengers about upcoming departure."""
        # Notify driver
        NotificationService.create_notification(
            user=ride.driver,
            category=NotificationCategory.RIDE,
            notification_type='RIDE_DEPARTURE_REMINDER',
            title='Ride Departing Soon',
            message=f'Your ride from {ride.origin} departs in {hours_before} hour(s)',
            action_url=f'/rides/{ride.id}',
            ride=ride,
            priority=15
        )
        
        # Notify passengers
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        passengers = SeatBooking.objects.filter(
            ride=ride,
            status=SeatBookingStatus.CONFIRMED
        ).select_related('passenger')
        
        for seat_booking in passengers:
            NotificationService.create_notification(
                user=seat_booking.passenger,
                category=NotificationCategory.RIDE,
                notification_type='RIDE_DEPARTURE_REMINDER',
                title='Ride Departing Soon',
                message=f'Your ride from {ride.origin} departs in {hours_before} hour(s)',
                action_url=f'/rides/{ride.id}',
                ride=ride,
                priority=15
            )
    
    @staticmethod
    def notify_payment_received(payment):
        """Notify about successful payment."""
        # Skip if no booking associated
        if not payment.booking:
            return
        
        # Notify renter
        NotificationService.create_notification(
            user=payment.booking.renter,
            category=NotificationCategory.PAYMENT,
            notification_type='PAYMENT_RECEIVED',
            title='Payment Successful',
            message=f'Payment of {payment.currency} {payment.amount} for {payment.booking.asset.name} was successful',
            action_url=f'/bookings/{payment.booking.id}',
            booking=payment.booking,
            priority=10
        )
        
        # Notify owner
        NotificationService.create_notification(
            user=payment.booking.asset.owner,
            category=NotificationCategory.PAYMENT,
            notification_type='PAYMENT_RECEIVED',
            title='Payment Received',
            message=f'Payment of {payment.currency} {payment.amount} received for {payment.booking.asset.name}',
            action_url=f'/bookings/{payment.booking.id}',
            booking=payment.booking,
            priority=10
        )
    
    @staticmethod
    def notify_payment_refunded(payment, amount):
        """Notify about payment refund."""
        # Skip if no booking associated
        if not payment.booking:
            return
        
        NotificationService.create_notification(
            user=payment.booking.renter,
            category=NotificationCategory.PAYMENT,
            notification_type='PAYMENT_REFUNDED',
            title='Payment Refunded',
            message=f'Refund of {payment.currency} {amount} has been processed',
            action_url=f'/bookings/{payment.booking.id}',
            booking=payment.booking,
            priority=10
        )
    
    @staticmethod
    def notify_message_received(message):
        """Notify user about new message."""
        # Get the other participants in the thread
        for participant in message.thread.participants.exclude(id=message.sender.id):
            NotificationService.create_notification(
                user=participant,
                category=NotificationCategory.MESSAGE,
                notification_type='MESSAGE_RECEIVED',
                title='New Message',
                message=f'{message.sender.get_full_name()}: {message.content[:50]}...',
                action_url=f'/messages/{message.thread.id}',
                priority=5
            )
    
    @staticmethod
    def notify_rating_received(rating):
        """Notify user about new rating."""
        NotificationService.create_notification(
            user=rating.target,
            category=NotificationCategory.RATING,
            notification_type='RATING_RECEIVED',
            title='New Rating Received',
            message=f'You received a {rating.overall_rating}-star rating from {rating.rater.get_full_name()}',
            action_url=f'/profile',
            priority=5
        )
    
    @staticmethod
    def notify_verification_approved(user):
        """Notify user about verification approval."""
        NotificationService.create_notification(
            user=user,
            category=NotificationCategory.SYSTEM,
            notification_type='VERIFICATION_APPROVED',
            title='Verification Approved',
            message='Your identity verification has been approved!',
            action_url='/profile',
            priority=15
        )
    
    @staticmethod
    def notify_verification_rejected(user, reason=''):
        """Notify user about verification rejection."""
        message = 'Your identity verification was rejected.'
        if reason:
            message += f' Reason: {reason}'
        
        NotificationService.create_notification(
            user=user,
            category=NotificationCategory.SYSTEM,
            notification_type='VERIFICATION_REJECTED',
            title='Verification Rejected',
            message=message,
            action_url='/profile',
            priority=15
        )
    
    @staticmethod
    def notify_dispute_created(dispute):
        """Notify both parties about dispute creation."""
        # Notify initiator
        NotificationService.create_notification(
            user=dispute.initiated_by,
            category=NotificationCategory.PAYMENT,
            notification_type='DISPUTE_CREATED',
            title='Dispute Created',
            message=f'Your dispute for booking {dispute.booking.id} has been created',
            action_url=f'/bookings/{dispute.booking.id}',
            booking=dispute.booking,
            priority=15
        )
        
        # Notify other party
        other_user = dispute.booking.renter if dispute.initiated_by == dispute.booking.asset.owner else dispute.booking.asset.owner
        NotificationService.create_notification(
            user=other_user,
            category=NotificationCategory.PAYMENT,
            notification_type='DISPUTE_CREATED',
            title='Dispute Opened',
            message=f'A dispute has been opened for booking {dispute.booking.id}',
            action_url=f'/bookings/{dispute.booking.id}',
            booking=dispute.booking,
            priority=15
        )
    
    @staticmethod
    def notify_dispute_resolved(dispute, resolution):
        """Notify both parties about dispute resolution."""
        # Notify both parties
        for user in [dispute.initiated_by, dispute.booking.renter, dispute.booking.asset.owner]:
            if user:
                NotificationService.create_notification(
                    user=user,
                    category=NotificationCategory.PAYMENT,
                    notification_type='DISPUTE_RESOLVED',
                    title='Dispute Resolved',
                    message=f'The dispute for booking {dispute.booking.id} has been resolved',
                    action_url=f'/bookings/{dispute.booking.id}',
                    booking=dispute.booking,
                    priority=15
                )


# Convenience function for quick notification creation
def notify(user, category, notification_type, title, message, **kwargs):
    """
    Quick notification helper function.
    
    Usage:
        notify(user, 'BOOKING', 'BOOKING_CREATED', 'New Booking', 'You have a new booking')
    """
    category_map = {
        'BOOKING': NotificationCategory.BOOKING,
        'RIDE': NotificationCategory.RIDE,
        'PAYMENT': NotificationCategory.PAYMENT,
        'CONTRACT': NotificationCategory.CONTRACT,
        'MESSAGE': NotificationCategory.MESSAGE,
        'RATING': NotificationCategory.RATING,
        'SYSTEM': NotificationCategory.SYSTEM,
    }
    
    return NotificationService.create_notification(
        user=user,
        category=category_map.get(category, NotificationCategory.SYSTEM),
        notification_type=notification_type,
        title=title,
        message=message,
        **kwargs
    )

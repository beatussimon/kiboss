"""
Services for Ride-Sharing Module
"""
import logging
from django.db import transaction
from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus

logger = logging.getLogger(__name__)

class SeatBookingService:
    @classmethod
    def confirm_seat_booking(cls, booking, actor):
        """Confirm a seat booking and update status."""
        with transaction.atomic():
            if booking.status != SeatBookingStatus.RESERVED:
                raise ValueError(f"Cannot confirm booking in {booking.status} status")
            
            booking.status = SeatBookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])
            
            # Send notification
            try:
                from kiboss.apps.notifications.services import NotificationService
                NotificationService.notify_seat_booking_updated(booking)
            except Exception as e:
                logger.warning(f"Failed to send notification for seat booking confirmation: {e}")
            
            return booking

"""
Booking Service for KIBOSS

Implements the booking engine with:
- Redis locking for double-booking prevention
- Availability checking
- Pricing calculation
- State machine transitions
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError
from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError
from kiboss.apps.assets.models import Asset, AssetPricing, AssetAvailability
from kiboss.apps.bookings.models import Booking, BookingStatus, BookingTimeline

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Base exception for booking errors."""
    pass


class AvailabilityError(BookingError):
    """Raised when asset is not available."""
    pass


class BookingService:
    """
    Service for creating and managing bookings.
    """
    
    PAYMENT_TIMEOUT_MINUTES = 15
    DEFAULT_GRACE_PERIOD_MINUTES = 15

    @staticmethod
    def _json_safe(value):
        """Convert Decimal-rich structures to JSON-safe primitives."""
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: BookingService._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [BookingService._json_safe(v) for v in value]
        return value
    
    @classmethod
    def check_availability(cls, asset_id, start_time, end_time, quantity=1):
        """
        Check if an asset is available for the requested time slot.
        
        Args:
            asset_id: UUID of the asset
            start_time: datetime when rental begins
            end_time: datetime when rental ends
            quantity: number of units/seats requested
            
        Returns:
            tuple: (is_available, conflict_info)
        """
        asset = Asset.objects.get(id=asset_id, is_active=True)
        
        # Check if asset is listed
        if not asset.is_listed:
            return False, {"error": "Asset is not listed for booking"}
        
        # Check verification status if required
        if asset.verification_status != 'VERIFIED':
            return False, {"error": "Asset is not verified"}
        
        # Query overlapping bookings
        overlapping = Booking.objects.filter(
            asset=asset,
            status__in=[
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
                BookingStatus.ACTIVE
            ],
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        
        # Calculate total booked quantity
        total_booked = overlapping.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Get asset capacity
        capacity = asset.get_property('capacity', 1)
        available = capacity - total_booked
        
        if quantity > available:
            return False, {
                "error": "Insufficient availability",
                "available": available,
                "requested": quantity,
                "conflicts": [
                    {
                        "booking_id": str(b.id),
                        "start_time": b.start_time.isoformat(),
                        "end_time": b.end_time.isoformat(),
                        "quantity": b.quantity
                    }
                    for b in overlapping
                ]
            }
        
        return True, {"available": available}
    
    @classmethod
    def calculate_price(cls, asset_id, quantity, start_time, end_time):
        """
        Calculate the total price for a booking.
        
        Args:
            asset_id: UUID of the asset
            quantity: number of units/seats
            start_time: datetime when rental begins
            end_time: datetime when rental ends
            
        Returns:
            dict: Price breakdown
        """
        asset = Asset.objects.get(id=asset_id)
        
        # Calculate duration in hours
        duration = end_time - start_time
        duration_hours = duration.total_seconds() / 3600
        
        # Find applicable pricing rule
        pricing_rule = AssetPricing.objects.filter(
            asset=asset,
            is_active=True
        ).order_by('-priority').first()
        
        if not pricing_rule:
            default_unit_price = Decimal(str(asset.get_property('default_price', '100.00')))
            base_price = default_unit_price * Decimal(str(quantity)) * Decimal(str(duration_hours))
            service_fee = base_price * Decimal('0.10')
            tax_rate = Decimal(str(asset.get_property('tax_rate', '0.00')))
            taxes = (base_price + service_fee) * tax_rate
            total = base_price + service_fee + taxes
            return {
                "unit_price": default_unit_price,
                "quantity": quantity,
                "duration_hours": duration_hours,
                "base_price": base_price,
                "subtotal": base_price,
                "service_fee": service_fee,
                "tax_rate": float(tax_rate),
                "taxes": taxes,
                "total": total,
                "currency": "USD"
            }
        
        # Calculate base price
        base_price = pricing_rule.calculate_price(
            quantity=quantity,
            duration_minutes=int(duration.total_seconds() / 60),
            start_time=start_time,
            end_time=end_time
        )
        
        # Apply quantity discount if applicable
        subtotal = base_price
        
        # Calculate service fee (10%)
        service_fee = subtotal * Decimal('0.10')
        
        # Calculate taxes (based on jurisdiction)
        tax_rate = asset.get_property('tax_rate', Decimal('0.00'))
        taxes = (subtotal + service_fee) * tax_rate
        
        total = subtotal + service_fee + taxes
        
        return {
            "unit_price": pricing_rule.price,
            "quantity": quantity,
            "duration_hours": duration_hours,
            "base_price": base_price,
            "subtotal": subtotal,
            "service_fee": service_fee,
            "tax_rate": float(tax_rate),
            "taxes": taxes,
            "total": total,
            "currency": "USD"
        }
    
    @classmethod
    def create_booking(cls, renter, asset_id, start_time, end_time, 
                      quantity=1, notes='', payment_method=None):
        """
        Create a new booking with Redis locking.
        
        Args:
            renter: User making the booking
            asset_id: UUID of the asset
            start_time: datetime when rental begins
            end_time: datetime when rental ends
            quantity: number of units/seats
            notes: optional renter notes
            payment_method: payment method details
            
        Returns:
            Booking: Created booking object
            
        Raises:
            AvailabilityError: If asset is not available
            LockAcquisitionError: If cannot acquire lock
        """
        # Check rate limit
        from kiboss.apps.common.locking import get_rate_limiter
        rate_limiter = get_rate_limiter()
        is_allowed, remaining, _ = rate_limiter.check_booking_rate_limit(str(renter.id))
        if not is_allowed:
            raise BookingError("Rate limit exceeded for booking creation")
        
        # Validate input
        if start_time >= end_time:
            raise BookingError("End time must be after start time")
        
        if start_time < timezone.now():
            raise BookingError("Cannot book in the past")
        
        if quantity < 1:
            raise BookingError("Quantity must be at least 1")
        
        # Get asset
        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise BookingError("Asset not found or not available")
        
        # Check ownership
        if asset.owner == renter:
            raise BookingError("Cannot book your own asset")
        
        # Acquire Redis lock for availability check
        lock_key = f"lock:asset:{asset_id}"
        lock_manager = get_lock_manager()
        
        def _do_booking():
            # Check availability with lock held
            is_available, info = cls.check_availability(
                asset_id, start_time, end_time, quantity
            )
            
            if not is_available:
                raise AvailabilityError(info.get("error", "Asset not available"))
            
            # Calculate price
            price_breakdown = cls.calculate_price(
                asset_id, quantity, start_time, end_time
            )
            
            # Create booking in transaction
            with transaction.atomic():
                booking = Booking.objects.create(
                    renter=renter,
                    asset=asset,
                    status=BookingStatus.PENDING,
                    start_time=start_time,
                    end_time=end_time,
                    quantity=quantity,
                    unit_price=price_breakdown["unit_price"],
                    subtotal=price_breakdown["subtotal"],
                    service_fee=price_breakdown["service_fee"],
                    taxes=price_breakdown["taxes"],
                    total_price=price_breakdown["total"],
                    price_breakdown=cls._json_safe(price_breakdown),
                    renter_notes=notes,
                    grace_period_minutes=cls.DEFAULT_GRACE_PERIOD_MINUTES
                )
                
                # Log timeline event
                BookingTimeline.log_event(
                    booking,
                    'CREATED',
                    f'Booking created for {asset.name}',
                    'USER',
                    renter.id,
                    {'quantity': quantity, 'total': str(price_breakdown["total"])}
                )
                
                return booking
        
        try:
            with lock_manager.lock(lock_key, ttl=30, max_retries=3):
                booking = _do_booking()
                
                # Schedule payment timeout task
                try:
                    from kiboss.apps.bookings.tasks import expire_pending_bookings
                    expire_pending_bookings.apply_async(
                        args=[booking.id],
                        countdown=cls.PAYMENT_TIMEOUT_MINUTES * 60
                    )
                except Exception as e:
                    logger.warning(f"Could not schedule expiry task: {e}")
                
                logger.info(f"Created booking {booking.id} for asset {asset_id}")
                return booking
                
        except LockAcquisitionError:
            raise BookingError(
                "Unable to process booking. Please try again."
            )
    
    @classmethod
    def confirm_booking(cls, booking_id, actor, justification=''):
        """
        Confirm a booking (transition PENDING -> CONFIRMED).
        
        Args:
            booking_id: UUID of the booking
            actor: User confirming the booking
            justification: Required for admin overrides
            
        Returns:
            Booking: Updated booking
            
        Raises:
            ValueError: If transition is invalid
        """
        booking = Booking.objects.select_for_update().get(id=booking_id)
        
        if booking.status != BookingStatus.PENDING:
            raise ValueError(f"Cannot confirm booking in {booking.status} status")
        
        # Transition to confirmed
        booking.transition_to(
            BookingStatus.CONFIRMED,
            actor_type='USER',
            actor_id=actor.id,
            reason='Booking confirmed',
            justification=justification
        )
        
        # Log timeline
        BookingTimeline.log_event(
            booking,
            'CONFIRMED',
            'Booking confirmed',
            'USER',
            actor.id
        )
        
        logger.info(f"Booking {booking_id} confirmed by {actor.email}")
        return booking
    
    @classmethod
    def cancel_booking(cls, booking_id, actor, reason='', justification=''):
        """
        Cancel a booking.
        
        Args:
            booking_id: UUID of the booking
            actor: User cancelling the booking
            reason: Reason for cancellation
            justification: Required for admin overrides
            
        Returns:
            Booking: Updated booking
            
        Raises:
            ValueError: If transition is invalid
        """
        booking = Booking.objects.select_for_update().get(id=booking_id)
        
        # Check if cancellable
        if booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
            raise ValueError(f"Cannot cancel booking in {booking.status} status")
        
        # Calculate cancellation fee
        if booking.status == BookingStatus.CONFIRMED:
            fee = booking.get_cancellation_fee(timezone.now())
        else:
            fee = Decimal('0.00')
        
        # Perform transition
        try:
            booking.transition_to(
                BookingStatus.CANCELLED,
                actor_type='USER' if not actor.is_staff else 'ADMIN',
                actor_id=actor.id,
                reason=reason,
                justification=justification
            )
        except ValueError as e:
            raise ValueError(str(e))
        
        # Update cancellation fee
        booking.cancellation_fee = fee
        booking.save()
        
        # Log timeline
        BookingTimeline.log_event(
            booking,
            'CANCELLED',
            f'Booking cancelled. Cancellation fee: {fee}',
            'USER' if not actor.is_staff else 'ADMIN',
            actor.id,
            {'reason': reason, 'fee': str(fee)}
        )
        
        logger.info(f"Booking {booking_id} cancelled by {actor.email}. Fee: {fee}")
        return booking
    
    @classmethod
    def start_booking(cls, booking_id, actor):
        """
        Start a booking (transition CONFIRMED -> ACTIVE).
        
        Args:
            booking_id: UUID of the booking
            actor: User starting the booking
            
        Returns:
            Booking: Updated booking
        """
        booking = Booking.objects.select_for_update().get(id=booking_id)
        
        if booking.status != BookingStatus.CONFIRMED:
            raise ValueError(f"Cannot start booking in {booking.status} status")
        
        booking.transition_to(
            BookingStatus.ACTIVE,
            actor_type='USER',
            actor_id=actor.id,
            reason='Rental period started'
        )
        
        BookingTimeline.log_event(
            booking,
            'STARTED',
            'Booking started',
            'USER',
            actor.id
        )
        
        return booking
    
    @classmethod
    def complete_booking(cls, booking_id, actor, notes='', late_return=False):
        """
        Complete a booking (transition ACTIVE -> COMPLETED).
        
        Args:
            booking_id: UUID of the booking
            actor: User completing the booking
            notes: Completion notes
            late_return: Whether return was late
            
        Returns:
            Booking: Updated booking
        """
        booking = Booking.objects.select_for_update().get(id=booking_id)
        
        if booking.status != BookingStatus.ACTIVE:
            raise ValueError(f"Cannot complete booking in {booking.status} status")
        
        return_time = timezone.now()
        
        # Calculate late fees if applicable
        if late_return or return_time > booking.end_time:
            late_fee = booking.calculate_late_fee(return_time)
            booking.is_late = True
            booking.late_minutes = int(
                (return_time - booking.end_time).total_seconds() / 60
            )
            booking.late_fee_charged = late_fee
        else:
            late_fee = Decimal('0.00')
        
        booking.transition_to(
            BookingStatus.COMPLETED,
            actor_type='USER',
            actor_id=actor.id,
            reason='Rental completed'
        )
        
        booking.completed_at = return_time
        booking.actual_return_time = return_time
        booking.save()
        
        BookingTimeline.log_event(
            booking,
            'COMPLETED',
            f'Booking completed. Late fee: {late_fee}',
            'USER',
            actor.id,
            {'late_return': late_return, 'late_fee': str(late_fee)}
        )
        
        # Update asset statistics
        with transaction.atomic():
            asset = Asset.objects.select_for_update().get(id=booking.asset.id)
            asset.total_bookings += 1
            asset.save(update_fields=['total_bookings', 'updated_at'])
        
        return booking


# Import models at module level to avoid circular imports
from django.db import models

"""
Unit tests for Booking models.

Tests cover:
- Booking state machine transitions
- Cancellation fee calculation
- Late fee calculation
- Timeline logging
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from kiboss.apps.bookings.models import (
    Booking, BookingStatus, BookingStatusTransition,
    BookingTimeline, BookingLock
)


class TestBookingModel:
    """Tests for the Booking model."""
    
    def test_create_booking(self, db, second_user, test_asset):
        """Test creating a booking."""
        start = timezone.now() + timedelta(days=1)
        booking = Booking.objects.create(
            renter=second_user,
            asset=test_asset,
            status=BookingStatus.PENDING,
            start_time=start,
            end_time=start + timedelta(hours=2),
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('200.00'),
            total_price=Decimal('220.00')
        )
        assert booking.renter == second_user
        assert booking.status == BookingStatus.PENDING
        assert booking.quantity == 1
    
    def test_booking_string_representation(self, db, test_booking):
        """Test booking string representation."""
        string_repr = str(test_booking)
        assert 'Booking' in string_repr
        assert test_booking.status in string_repr
    
    def test_transition_pending_to_confirmed(self, db, test_booking):
        """Test transitioning from PENDING to CONFIRMED."""
        assert test_booking.status == BookingStatus.PENDING
        
        success = test_booking.transition_to(
            BookingStatus.CONFIRMED,
            actor_type='USER',
            actor_id=test_booking.renter_id,
            reason='Payment confirmed'
        )
        
        assert success is True
        test_booking.refresh_from_db()
        assert test_booking.status == BookingStatus.CONFIRMED
        
        # Check transition was logged
        transition = BookingStatusTransition.objects.get(
            booking=test_booking,
            from_status=BookingStatus.PENDING,
            to_status=BookingStatus.CONFIRMED
        )
        assert transition.actor_type == 'USER'
    
    def test_transition_invalid_from_pending(self, db, test_booking):
        """Test invalid transition from PENDING."""
        with pytest.raises(ValueError, match='Invalid transition'):
            test_booking.transition_to(
                BookingStatus.COMPLETED,
                actor_type='SYSTEM'
            )
    
    def test_transition_confirmed_to_active(self, db, confirmed_booking):
        """Test transitioning from CONFIRMED to ACTIVE."""
        assert confirmed_booking.status == BookingStatus.CONFIRMED
        
        success = confirmed_booking.transition_to(
            BookingStatus.ACTIVE,
            actor_type='SYSTEM'
        )
        
        assert success is True
        confirmed_booking.refresh_from_db()
        assert confirmed_booking.status == BookingStatus.ACTIVE
    
    def test_transition_active_to_completed(self, db, confirmed_booking):
        """Test transitioning from ACTIVE to COMPLETED."""
        # First transition to ACTIVE
        confirmed_booking.transition_to(BookingStatus.ACTIVE, actor_type='SYSTEM')
        
        # Then to COMPLETED
        success = confirmed_booking.transition_to(
            BookingStatus.COMPLETED,
            actor_type='USER'
        )
        
        assert success is True
        confirmed_booking.refresh_from_db()
        assert confirmed_booking.status == BookingStatus.COMPLETED
        assert confirmed_booking.completed_at is not None
    
    def test_transition_requires_admin_justification(self, db, test_booking):
        """Test that admin transitions require justification."""
        with pytest.raises(ValueError, match='requires justification'):
            test_booking.transition_to(
                BookingStatus.CANCELLED,
                actor_type='ADMIN'
            )
        
        # With justification, it should work
        success = test_booking.transition_to(
            BookingStatus.CANCELLED,
            actor_type='ADMIN',
            justification='Test admin cancellation'
        )
        assert success is True
    
    def test_is_cancellable(self, db, test_booking, confirmed_booking):
        """Test is_cancellable method."""
        # Pending booking should be cancellable
        can_cancel, _ = test_booking.is_cancellable()
        assert can_cancel is True
        
        # Confirmed booking should be cancellable
        can_cancel, _ = confirmed_booking.is_cancellable()
        assert can_cancel is True
    
    def test_is_not_cancellable_when_active(self, db, confirmed_booking):
        """Test that active bookings cannot be cancelled."""
        confirmed_booking.status = BookingStatus.ACTIVE
        confirmed_booking.save()
        
        can_cancel, reason = confirmed_booking.is_cancellable()
        assert can_cancel is False
        assert 'ACTIVE' in reason
    
    def test_is_startable(self, db, test_booking, confirmed_booking):
        """Test is_startable method."""
        # Pending booking cannot start
        can_start, _ = test_booking.is_startable()
        assert can_start is False
        
        # Confirmed booking can start
        can_start, _ = confirmed_booking.is_startable()
        assert can_start is True
    
    def test_is_completable(self, db, confirmed_booking):
        """Test is_completable method."""
        # Confirmed booking cannot complete
        can_complete, _ = confirmed_booking.is_completable()
        assert can_complete is False
        
        # Active booking can complete
        confirmed_booking.status = BookingStatus.ACTIVE
        confirmed_booking.save()
        
        can_complete, _ = confirmed_booking.is_completable()
        assert can_complete is True


class TestBookingCalculations:
    """Tests for booking calculations."""
    
    def test_get_duration_hours(self, db, test_booking):
        """Test getting booking duration in hours."""
        duration = test_booking.get_duration_hours()
        assert duration == 2.0
    
    def test_get_cancellation_fee_early(self, db, test_booking):
        """Test cancellation fee when cancelling early (>48 hours)."""
        fee = test_booking.get_cancellation_fee(timezone.now())
        assert fee == Decimal('0.00')
    
    def test_get_cancellation_fee_medium(self, db, test_booking):
        """Test cancellation fee (24-48 hours)."""
        # Set start time to 36 hours from now
        test_booking.start_time = timezone.now() + timedelta(hours=36)
        test_booking.save()
        
        fee = test_booking.get_cancellation_fee(timezone.now())
        assert fee == test_booking.subtotal * Decimal('0.25')
    
    def test_get_cancellation_fee_late(self, db, test_booking):
        """Test cancellation fee when cancelling late (<2 hours)."""
        # Set start time to 1 hour from now
        test_booking.start_time = timezone.now() + timedelta(hours=1)
        test_booking.save()
        
        fee = test_booking.get_cancellation_fee(timezone.now())
        assert fee == test_booking.subtotal
    
    def test_calculate_late_fee(self, db, test_booking):
        """Test calculating late fee."""
        test_booking.is_late = True
        test_booking.late_fee_per_unit = Decimal('10.00')
        test_booking.late_fee_max = Decimal('50.00')
        test_booking.save()
        
        # Return 3 hours late (30 * 10 = 300, capped at 50)
        return_time = test_booking.end_time + timedelta(hours=3)
        fee = test_booking.calculate_late_fee(return_time)
        
        assert fee == Decimal('50.00')  # Max cap
    
    def test_calculate_late_fee_under_max(self, db, test_booking):
        """Test late fee under maximum."""
        test_booking.is_late = True
        test_booking.late_fee_per_unit = Decimal('5.00')
        test_booking.late_fee_max = Decimal('50.00')
        test_booking.save()
        
        # Return 2 hours late (2 * 5 * 1 = 10)
        return_time = test_booking.end_time + timedelta(hours=2)
        fee = test_booking.calculate_late_fee(return_time)
        
        assert fee == Decimal('10.00')


class TestBookingTimeline:
    """Tests for booking timeline."""
    
    def test_log_event(self, db, test_booking):
        """Test logging a timeline event."""
        event = BookingTimeline.log_event(
            booking=test_booking,
            event_type='CREATED',
            description='Booking created',
            actor_type='USER',
            actor_id=test_booking.renter_id,
            data={'source': 'web'}
        )
        
        assert event.booking == test_booking
        assert event.event_type == 'CREATED'
        assert event.data == {'source': 'web'}
    
    def test_timeline_ordering(self, db, test_booking):
        """Test that timeline events are ordered by creation time."""
        # Create multiple events
        for i in range(3):
            BookingTimeline.log_event(
                booking=test_booking,
                event_type='TEST_EVENT',
                description=f'Event {i}',
                actor_type='SYSTEM'
            )
        
        events = list(test_booking.timeline_events.all())
        assert len(events) == 3
        
        # Events should be in ascending order (oldest first)
        for i in range(len(events) - 1):
            assert events[i].created_at <= events[i + 1].created_at


class TestBookingLock:
    """Tests for booking locks."""
    
    def test_create_lock(self, db, test_booking, test_user):
        """Test creating a booking lock."""
        lock = BookingLock.objects.create(
            lock_type='BOOKING',
            resource_type='booking',
            resource_id=test_booking.id,
            owner_id=test_user.id,
            owner_process='test_process_123',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        assert lock.lock_type == 'BOOKING'
        assert lock.resource_type == 'booking'

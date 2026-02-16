"""
Unit tests for Ride models.

Tests cover:
- Ride creation and lifecycle
- Seat booking management
- Ride availability
- Schedule generation
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta, datetime

from kiboss.apps.rides.models import (
    Ride, RideStatus, RideStop, SeatBooking,
    SeatBookingStatus, RideSchedule
)


class TestRideModel:
    """Tests for the Ride model."""
    
    def test_create_ride(self, db, test_user, test_asset_vehicle):
        """Test creating a ride."""
        ride = Ride.objects.create(
            driver=test_user,
            vehicle_asset=test_asset_vehicle,
            status=RideStatus.SCHEDULED,
            route_name='Test Route',
            origin='New York',
            destination='Boston',
            departure_time=timezone.now() + timedelta(days=1),
            total_seats=4,
            seat_price=Decimal('25.00')
        )
        assert ride.driver == test_user
        assert ride.status == RideStatus.SCHEDULED
        assert ride.total_seats == 4
        assert ride.confirmed_seats == 0
        assert str(ride).startswith('Ride')
    
    def test_get_available_seats(self, db, test_ride):
        """Test getting available seats."""
        assert test_ride.get_available_seats() == 4
        
        test_ride.confirmed_seats = 2
        test_ride.save()
        
        assert test_ride.get_available_seats() == 2
    
    def test_is_full(self, db, test_ride):
        """Test checking if ride is full."""
        test_ride.confirmed_seats = 3
        test_ride.save()
        assert test_ride.is_full() is False
        
        test_ride.confirmed_seats = 4
        test_ride.save()
        assert test_ride.is_full() is True
    
    def test_can_book_open_ride(self, db, open_ride):
        """Test booking open ride."""
        can_book, reason = open_ride.can_book()
        assert can_book is True
        assert reason is None
    
    def test_cannot_book_full_ride(self, db, test_user, test_asset_vehicle):
        """Test cannot book full ride."""
        ride = Ride.objects.create(
            driver=test_user,
            vehicle_asset=test_asset_vehicle,
            status=RideStatus.FULL,
            route_name='Full Ride',
            origin='A',
            destination='B',
            departure_time=timezone.now() + timedelta(days=1),
            total_seats=3,
            seat_price=Decimal('20.00'),
            confirmed_seats=3
        )
        can_book, reason = ride.can_book()
        assert can_book is False
        assert 'full' in reason.lower()
    
    def test_cannot_book_past_ride(self, db, test_user, test_asset_vehicle):
        """Test cannot book ride that has departed."""
        ride = Ride.objects.create(
            driver=test_user,
            vehicle_asset=test_asset_vehicle,
            status=RideStatus.SCHEDULED,
            route_name='Past Ride',
            origin='A',
            destination='B',
            departure_time=timezone.now() - timedelta(hours=1),  # Past
            total_seats=4,
            seat_price=Decimal('20.00')
        )
        can_book, reason = ride.can_book()
        assert can_book is False
        assert 'departed' in reason.lower()


class TestRideStopModel:
    """Tests for the RideStop model."""
    
    def test_create_ride_stop(self, db, test_ride):
        """Test creating a ride stop."""
        stop = RideStop.objects.create(
            ride=test_ride,
            stop_type='PICKUP',
            name='Times Square',
            address='Times Square, NYC',
            latitude=Decimal('40.7580'),
            longitude=Decimal('-73.9855'),
            stop_order=1
        )
        assert stop.stop_type == 'PICKUP'
        assert stop.stop_order == 1
        assert str(stop).startswith('Stop 1')
    
    def test_ride_stops_ordered(self, db, test_ride_with_stops):
        """Test that stops are ordered correctly."""
        stops = list(test_ride_with_stops.stops.all())
        assert len(stops) == 2
        assert stops[0].stop_order == 1
        assert stops[1].stop_order == 2


class TestSeatBookingModel:
    """Tests for the SeatBooking model."""
    
    def test_create_seat_booking(self, db, open_ride, second_user):
        """Test creating a seat booking."""
        booking = SeatBooking.objects.create(
            ride=open_ride,
            passenger=second_user,
            seat_number=1,
            status=SeatBookingStatus.RESERVED,
            price=Decimal('30.00')
        )
        assert booking.passenger == second_user
        assert booking.seat_number == 1
        assert booking.status == SeatBookingStatus.RESERVED
    
    def test_cancel_seat_booking(self, db, open_ride, second_user):
        """Test cancelling a seat booking."""
        booking = SeatBooking.objects.create(
            ride=open_ride,
            passenger=second_user,
            seat_number=1,
            status=SeatBookingStatus.CONFIRMED,
            price=Decimal('30.00')
        )
        open_ride.confirmed_seats = 1
        open_ride.save()
        
        booking.cancel('Test cancellation')
        
        booking.refresh_from_db()
        assert booking.status == SeatBookingStatus.CANCELLED
        assert booking.cancelled_at is not None
        
        open_ride.refresh_from_db()
        assert open_ride.confirmed_seats == 0
    
    def test_cannot_cancel_already_cancelled(self, db, open_ride, second_user):
        """Test cannot cancel already cancelled booking."""
        booking = SeatBooking.objects.create(
            ride=open_ride,
            passenger=second_user,
            seat_number=1,
            status=SeatBookingStatus.CANCELLED,
            price=Decimal('30.00'),
            cancelled_at=timezone.now()
        )
        
        # This should not raise error but also not change anything
        booking.cancel('Double cancellation')
        booking.refresh_from_db()
        assert booking.status == SeatBookingStatus.CANCELLED
    
    def test_mark_no_show(self, db, open_ride, second_user):
        """Test marking passenger as no-show."""
        booking = SeatBooking.objects.create(
            ride=open_ride,
            passenger=second_user,
            seat_number=1,
            status=SeatBookingStatus.CONFIRMED,
            price=Decimal('30.00')
        )
        
        booking.mark_no_show()
        booking.refresh_from_db()
        
        assert booking.status == SeatBookingStatus.NO_SHOW
        assert booking.marked_no_show_at is not None
        assert booking.no_show_penalty_applied is True


class TestRideScheduleModel:
    """Tests for the RideSchedule model."""
    
    def test_create_ride_schedule(self, db, test_user):
        """Test creating a ride schedule."""
        schedule = RideSchedule.objects.create(
            driver=test_user,
            name='Daily Commute',
            schedule_type='WEEKLY',
            origin='Home',
            destination='Office',
            departure_time=datetime.strptime('08:00', '%H:%M').time(),
            estimated_duration_minutes=30,
            recurrence_days=[1, 2, 3, 4, 5],  # Mon-Fri
            total_seats=4,
            seat_price=Decimal('10.00'),
            valid_from=timezone.now().date()
        )
        assert schedule.name == 'Daily Commute'
        assert schedule.schedule_type == 'WEEKLY'
        assert len(schedule.recurrence_days) == 5
    
    def test_generate_rides(self, db, test_user, test_asset_vehicle):
        """Test generating rides from schedule."""
        schedule = RideSchedule.objects.create(
            driver=test_user,
            vehicle_asset=test_asset_vehicle,
            name='Daily Route',
            schedule_type='DAILY',
            origin='A',
            destination='B',
            departure_time=datetime.strptime('09:00', '%H:%M').time(),
            recurrence_days=[0, 1, 2, 3, 4, 5, 6],  # Every day
            total_seats=3,
            seat_price=Decimal('15.00'),
            valid_from=timezone.now().date()
        )
        
        rides = schedule.generate_rides(days_ahead=3)
        
        # Should generate rides for each day in range
        assert len(rides) >= 1
        assert all(isinstance(r, Ride) for r in rides)
    
    def test_generate_rides_respects_recurrence(self, db, test_user, test_asset_vehicle):
        """Test that generated rides respect recurrence days."""
        schedule = RideSchedule.objects.create(
            driver=test_user,
            vehicle_asset=test_asset_vehicle,
            name='Weekday Only',
            schedule_type='WEEKLY',
            origin='A',
            destination='B',
            departure_time=datetime.strptime('10:00', '%H:%M').time(),
            recurrence_days=[1, 3, 5],  # Wed, Fri, Sun
            total_seats=2,
            seat_price=Decimal('20.00'),
            valid_from=timezone.now().date()
        )
        
        rides = schedule.generate_rides(days_ahead=7)
        
        # Check that rides only created on scheduled days
        for ride in rides:
            departure_weekday = ride.departure_time.weekday()
            assert departure_weekday in [1, 3, 5]

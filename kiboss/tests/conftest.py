"""
Pytest configuration and fixtures for KIBOSS backend tests.

This module provides:
- Database fixtures
- User authentication fixtures
- API client fixtures
- Common test utilities
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from kiboss.apps.users.models import User, UserProfile, TrustScore, Device
from kiboss.apps.assets.models import (
    Asset, AssetType, VerificationStatus, AssetPricing,
    AssetAvailability, AssetCapacity, AssetPhoto
)
from kiboss.apps.rides.models import Ride, RideStatus, RideStop, SeatBooking, RideSchedule
from kiboss.apps.bookings.models import Booking, BookingStatus


# ============ User Fixtures ============

@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User.objects.create_user(
        email='testuser@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User',
        is_email_verified=True
    )
    return user


@pytest.fixture
def test_user_profile(db, test_user):
    """Create a test user profile."""
    profile, _ = UserProfile.objects.get_or_create(
        user=test_user,
        defaults={
            'phone': '+1234567890',
            'bio': 'Test user bio',
            'city': 'Test City',
            'country': 'US'
        }
    )
    return profile


@pytest.fixture
def test_trust_score(db, test_user):
    """Create a test trust score."""
    trust, _ = TrustScore.objects.get_or_create(
        user=test_user,
        defaults={
            'reliability_score': Decimal('75.00'),
            'communication_score': Decimal('80.00'),
            'cleanliness_score': Decimal('85.00'),
            'timeliness_score': Decimal('70.00'),
            'overall_score': Decimal('75.00')
        }
    )
    return trust


@pytest.fixture
def second_user(db):
    """Create a second test user."""
    return User.objects.create_user(
        email='seconduser@example.com',
        password='testpass456',
        first_name='Second',
        last_name='User'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email='admin@example.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def api_client(db):
    """Create a basic API client."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated API client."""
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def authenticated_client_second(api_client, second_user):
    """Create an authenticated API client for second user."""
    refresh = RefreshToken.for_user(second_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Create an authenticated admin API client."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# ============ Asset Fixtures ============

@pytest.fixture
def test_asset(db, test_user):
    """Create a test asset."""
    asset = Asset.objects.create(
        name='Test Apartment',
        description='A beautiful test apartment',
        asset_type=AssetType.ROOM,
        owner=test_user,
        address='123 Test Street',
        city='Test City',
        state='Test State',
        country='US',
        postal_code='12345',
        verification_status=VerificationStatus.VERIFIED,
        is_active=True,
        is_listed=True,
        properties={
            'room_type': 'DELUXE',
            'floor': 1,
            'max_guests': 2,
            'bedrooms': 2,
            'bathrooms': 1,
            'sqft': 1000
        }
    )
    return asset


@pytest.fixture
def test_asset_vehicle(db, test_user):
    """Create a test vehicle asset."""
    asset = Asset.objects.create(
        name='Test Car',
        description='A reliable test vehicle',
        asset_type=AssetType.VEHICLE,
        owner=test_user,
        address='123 Test Street',
        city='Test City',
        country='US',
        verification_status=VerificationStatus.VERIFIED,
        is_active=True,
        is_listed=True,
        properties={
            'make': 'Toyota',
            'model': 'Camry',
            'year': 2020,
            'mileage': 50000,
            'license_plate': 'TEST-123',
            'vehicle_type': 'SEDAN'
        }
    )
    from kiboss.apps.assets.models import AssetCapacity
    AssetCapacity.objects.create(
        asset=asset,
        capacity_type='SEAT',
        quantity=4,
        description='Passenger seats'
    )
    return asset


@pytest.fixture
def test_asset_pricing(db, test_asset):
    """Create test asset pricing."""
    pricing = AssetPricing.objects.create(
        asset=test_asset,
        name='Standard Rate',
        unit_type='DAY',
        price=Decimal('100.00'),
        min_quantity=1,
        max_quantity=30,
        min_duration_minutes=1440,  # 24 hours
        is_active=True
    )
    return pricing


@pytest.fixture
def test_asset_capacity(db, test_asset):
    """Create test asset capacity."""
    capacity = AssetCapacity.objects.create(
        asset=test_asset,
        capacity_type='GUEST',
        quantity=4,
        description='Maximum guest capacity'
    )
    return capacity


@pytest.fixture
def multiple_assets(db, test_user):
    """Create multiple test assets."""
    assets = []
    for i in range(5):
        asset = Asset.objects.create(
            name=f'Test Asset {i}',
            description=f'Description for asset {i}',
            asset_type=AssetType.ROOM,
            owner=test_user,
            city='Test City',
            country='US',
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            is_listed=True,
            properties={
                'room_type': 'STANDARD',
                'floor': i + 1,
                'max_guests': 2
            }
        )
        assets.append(asset)
    return assets


# ============ Ride Fixtures ============

@pytest.fixture
def test_ride(db, test_user, test_asset_vehicle):
    """Create a test ride."""
    ride = Ride.objects.create(
        driver=test_user,
        vehicle_asset=test_asset_vehicle,
        status=RideStatus.SCHEDULED,
        route_name='Test Route',
        origin='New York',
        destination='Boston',
        departure_time=timezone.now() + timedelta(days=1),
        total_seats=4,
        seat_price=Decimal('25.00'),
        currency='USD'
    )
    return ride


@pytest.fixture
def test_ride_with_stops(db, test_ride):
    """Create a test ride with stops."""
    RideStop.objects.create(
        ride=test_ride,
        stop_type='PICKUP',
        name='Times Square',
        address='Times Square, NYC',
        latitude=Decimal('40.7580'),
        longitude=Decimal('-73.9855'),
        stop_order=1
    )
    RideStop.objects.create(
        ride=test_ride,
        stop_type='DROPOFF',
        name='Boston Common',
        address='Boston Common, Boston',
        latitude=Decimal('42.3551'),
        longitude=Decimal('-71.0656'),
        stop_order=2
    )
    return test_ride


@pytest.fixture
def open_ride(db, test_user, test_asset_vehicle):
    """Create an open ride for booking."""
    ride = Ride.objects.create(
        driver=test_user,
        vehicle_asset=test_asset_vehicle,
        status=RideStatus.OPEN,
        route_name='Open Route',
        origin='San Francisco',
        destination='Los Angeles',
        departure_time=timezone.now() + timedelta(days=2),
        total_seats=3,
        seat_price=Decimal('30.00'),
        currency='USD'
    )
    return ride


# ============ Booking Fixtures ============

@pytest.fixture
def test_booking(db, second_user, test_asset):
    """Create a test booking."""
    start_time = timezone.now() + timedelta(days=3)
    end_time = start_time + timedelta(hours=2)
    
    booking = Booking.objects.create(
        renter=second_user,
        asset=test_asset,
        status=BookingStatus.PENDING,
        start_time=start_time,
        end_time=end_time,
        quantity=1,
        unit_price=Decimal('100.00'),
        subtotal=Decimal('200.00'),
        service_fee=Decimal('20.00'),
        taxes=Decimal('0.00'),
        total_price=Decimal('220.00'),
        currency='USD',
        price_breakdown={
            'base_price': '200.00',
            'service_fee': '20.00',
            'taxes': '0.00'
        }
    )
    return booking


@pytest.fixture
def confirmed_booking(db, test_booking):
    """Create a confirmed booking."""
    return Booking.objects.create(
        renter=test_booking.renter,
        asset=test_booking.asset,
        status=BookingStatus.CONFIRMED,
        start_time=test_booking.start_time,
        end_time=test_booking.end_time,
        quantity=test_booking.quantity,
        unit_price=test_booking.unit_price,
        subtotal=test_booking.subtotal,
        service_fee=test_booking.service_fee,
        taxes=test_booking.taxes,
        total_price=test_booking.total_price,
        currency=test_booking.currency,
        price_breakdown=test_booking.price_breakdown,
    )


# ============ Messaging Fixtures ============

@pytest.fixture
def test_thread(db, test_user, second_user):
    """Create a test message thread."""
    from kiboss.apps.messaging.models import Thread, ThreadType
    
    thread = Thread.objects.create(
        thread_type=ThreadType.DIRECT,
        subject='Test Thread',
        auto_lock_after_completion=False
    )
    thread.participants.add(test_user, second_user)
    return thread


# ============ Authentication Fixtures ============

@pytest.fixture
def user_credentials():
    """Return user login credentials."""
    return {
        'email': 'testuser@example.com',
        'password': 'testpass123'
    }


@pytest.fixture
def jwt_tokens(test_user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(test_user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'access_expiry': timezone.now() + timedelta(minutes=15),
        'refresh_expiry': timezone.now() + timedelta(days=7)
    }


# ============ Test Data Generation Fixtures ============

@pytest.fixture
def sample_booking_data(test_asset):
    """Return sample booking data for POST requests."""
    start_time = timezone.now() + timedelta(days=1)
    return {
        'asset_id': str(test_asset.id),
        'start_time': start_time.isoformat(),
        'end_time': (start_time + timedelta(hours=2)).isoformat(),
        'quantity': 1,
        'renter_notes': 'Test booking notes'
    }


@pytest.fixture
def sample_asset_data(test_user):
    """Return sample asset data for POST requests."""
    return {
        'name': 'New Test Asset',
        'description': 'A new test asset description',
        'asset_type': 'ROOM',
        'address': '456 New Street',
        'city': 'New City',
        'state': 'New State',
        'country': 'US',
        'postal_code': '54321',
        'properties': {
            'room_type': 'STANDARD',
            'floor': 1,
            'max_guests': 2,
            'bedrooms': 3,
            'bathrooms': 2
        }
    }


@pytest.fixture
def sample_ride_data(test_user, test_asset_vehicle):
    """Return sample ride data for POST requests."""
    departure = timezone.now() + timedelta(days=3)
    return {
        'vehicle_asset_id': str(test_asset_vehicle.id),
        'route_name': 'New Test Route',
        'origin': 'Chicago',
        'destination': 'Detroit',
        'departure_time': departure.isoformat(),
        'total_seats': 4,
        'seat_price': '20.00',
        'currency': 'USD'
    }


# ============ Edge Case Fixtures ============

@pytest.fixture
def inactive_user(db):
    """Create an inactive user."""
    return User.objects.create_user(
        email='inactive@example.com',
        password='inactive123',
        is_active=False
    )


@pytest.fixture
def blocked_user(db):
    """Create a blocked user."""
    user = User.objects.create_user(
        email='blocked@example.com',
        password='blocked123'
    )
    user.is_blocked = True
    user.block_reason = 'Test block'
    user.save()
    return user


@pytest.fixture
def unverified_asset(db, test_user):
    """Create an unverified asset."""
    return Asset.objects.create(
        name='Unverified Asset',
        description='Awaiting verification',
        asset_type=AssetType.ROOM,
        owner=test_user,
        verification_status=VerificationStatus.UNVERIFIED,
        is_active=True,
        is_listed=True,
        properties={
            'room_type': 'STANDARD',
            'floor': 1,
            'max_guests': 2
        }
    )

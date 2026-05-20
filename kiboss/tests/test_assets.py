"""
Unit tests for Asset models.

Tests cover:
- Asset creation and validation
- Asset type-specific behaviors
- Pricing calculations
- Availability checking
- Capacity management
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from kiboss.apps.assets.models import (
    Asset, AssetType, VerificationStatus,
    AssetPricing, AssetAvailability, AssetCapacity,
    AssetTimeGranularity, AssetPhoto, AssetLike
)


class TestAssetModel:
    """Tests for the Asset model."""
    
    def test_create_room_asset(self, db, test_user):
        """Test creating a room asset."""
        asset = Asset.objects.create(
            name='Test Room',
            description='A test room',
            asset_type=AssetType.ROOM,
            owner=test_user,
            city='Test City',
            country='US',
            properties={
                'room_type': 'DELUXE',
                'floor': 1,
                'max_guests': 2
            }
        )
        assert asset.name == 'Test Room'
        assert asset.asset_type == AssetType.ROOM
        assert asset.verification_status == VerificationStatus.UNVERIFIED
        assert asset.is_active is True
        assert asset.is_listed is True
        assert str(asset) == 'Test Room (Room/Space)'
    
    def test_create_vehicle_asset(self, db, test_user):
        """Test creating a vehicle asset."""
        asset = Asset.objects.create(
            name='Test Vehicle',
            asset_type=AssetType.VEHICLE,
            owner=test_user,
            properties={
                'make': 'Toyota',
                'model': 'Camry',
                'year': 2020,
                'license_plate': 'TEST-123',
                'vehicle_type': 'SEDAN'
            }
        )
        assert asset.asset_type == AssetType.VEHICLE
        assert asset.get_property('make') == 'Toyota'
        assert asset.get_property('model') == 'Camry'
    
    def test_set_property(self, db, test_asset):
        """Test setting asset properties."""
        test_asset.set_property('new_key', 'new_value')
        test_asset.refresh_from_db()
        assert test_asset.get_property('new_key') == 'new_value'
    
    def test_get_property_with_default(self, db, test_asset):
        """Test getting property with default value."""
        value = test_asset.get_property('nonexistent', 'default')
        assert value == 'default'
    
    def test_update_average_rating(self, db, test_user):
        """Test updating average rating."""
        asset = Asset.objects.create(
            name='Test Asset',
            asset_type=AssetType.ROOM,
            owner=test_user,
            average_rating=Decimal('4.00'),
            total_reviews=10,
            properties={
                'room_type': 'DELUXE',
                'floor': 1,
                'max_guests': 2
            }
        )
        
        # Simulate new review
        asset.average_rating = Decimal('4.5')
        asset.total_reviews = 11
        asset.save()
        
        asset.refresh_from_db()
        assert asset.average_rating == Decimal('4.50')
        assert asset.total_reviews == 11


class TestAssetPricingModel:
    """Tests for the AssetPricing model."""
    
    def test_create_pricing(self, db, test_asset):
        """Test creating asset pricing."""
        pricing = AssetPricing.objects.create(
            asset=test_asset,
            name='Daily Rate',
            unit_type='DAY',
            price=Decimal('100.00'),
            min_quantity=1,
            max_quantity=30
        )
        assert pricing.name == 'Daily Rate'
        assert pricing.unit_type == 'DAY'
        assert pricing.price == Decimal('100.00')
        assert str(pricing) == f'{test_asset.name} - Daily Rate (100.00/day)'
    
    def test_calculate_price_basic(self, db, test_asset):
        """Test basic price calculation."""
        pricing = AssetPricing.objects.create(
            asset=test_asset,
            name='Standard',
            unit_type='DAY',
            price=Decimal('100.00'),
            quantity_discounts=[
                {'min_quantity': 3, 'multiplier': 0.9},  # 10% off for 3+ days
                {'min_quantity': 7, 'multiplier': 0.8}   # 20% off for 7+ days
            ]
        )
        
        # No discount
        assert pricing.calculate_price(1) == Decimal('100.00')
        
        # 10% discount
        assert pricing.calculate_price(3) == Decimal('270.00')  # 100 * 3 * 0.9
        
        # 20% discount
        assert pricing.calculate_price(7) == Decimal('560.00')  # 100 * 7 * 0.8
    
    def test_calculate_price_with_quantity(self, db, test_asset):
        """Test price calculation with quantity."""
        pricing = AssetPricing.objects.create(
            asset=test_asset,
            name='Per Seat',
            unit_type='SEAT',
            price=Decimal('25.00')
        )
        
        # 2 seats
        assert pricing.calculate_price(2) == Decimal('50.00')


class TestAssetAvailabilityModel:
    """Tests for the AssetAvailability model."""
    
    def test_create_availability(self, db, test_asset):
        """Test creating asset availability."""
        availability = AssetAvailability.objects.create(
            asset=test_asset,
            name='Standard Availability',
            availability_type='SCHEDULED',
            buffer_minutes=30,
            min_advance_booking_minutes=60,
            max_advance_booking_days=90,
            blocked_dates=['2024-12-25', '2025-01-01']
        )
        assert availability.availability_type == 'SCHEDULED'
        assert availability.buffer_minutes == 30
        assert '2024-12-25' in availability.blocked_dates
    
    def test_is_available_default(self, db, test_asset):
        """Test default availability check."""
        availability = AssetAvailability.objects.create(
            asset=test_asset,
            name='Standard Availability',
            availability_type='SCHEDULED',
            buffer_minutes=0
        )
        
        # Test within a generic window that should be available if no bookings exist
        is_available, reason = availability.is_available(
            timezone.now() + timedelta(days=10),
            timezone.now() + timedelta(days=10, hours=2)
        )
        assert is_available is True
        assert reason is None


class TestAssetCapacityModel:
    """Tests for the AssetCapacity model."""
    
    def test_create_capacity(self, db, test_asset):
        """Test creating asset capacity."""
        capacity = AssetCapacity.objects.create(
            asset=test_asset,
            capacity_type='GUEST',
            quantity=4,
            description='Maximum guests'
        )
        assert capacity.capacity_type == 'GUEST'
        assert capacity.quantity == 4
        assert str(capacity) == f'{test_asset.name} - Guest capacity: 4'


class TestAssetTimeGranularityModel:
    """Tests for the AssetTimeGranularity model."""
    
    def test_create_time_granularity(self, db, test_asset):
        """Test creating time granularity."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            max_duration_minutes=480,
            increment_minutes=30,
            any_start_time=True,
            same_day_booking=True,
            cutoff_hour=18
        )
        assert granularity.min_duration_minutes == 60
        assert granularity.increment_minutes == 30
    
    def test_validate_duration_valid(self, db, test_asset):
        """Test valid duration validation."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            max_duration_minutes=240,
            increment_minutes=60
        )
        
        is_valid, _ = granularity.validate_duration(120)
        assert is_valid is True
    
    def test_validate_duration_below_minimum(self, db, test_asset):
        """Test duration below minimum."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            increment_minutes=60
        )
        
        is_valid, reason = granularity.validate_duration(30)
        assert is_valid is False
        assert 'at least 60 minutes' in reason
    
    def test_validate_duration_exceeds_maximum(self, db, test_asset):
        """Test duration exceeds maximum."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            max_duration_minutes=240,
            increment_minutes=60
        )
        
        is_valid, reason = granularity.validate_duration(300)
        assert is_valid is False
        assert 'cannot exceed 240 minutes' in reason
    
    def test_validate_duration_invalid_increment(self, db, test_asset):
        """Test duration with invalid increment."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            max_duration_minutes=240,
            increment_minutes=60
        )
        
        is_valid, reason = granularity.validate_duration(90)
        assert is_valid is False
        assert '60 minute increments' in reason
    
    def test_validate_start_time_with_restrictions(self, db, test_asset):
        """Test start time validation with restrictions."""
        granularity = AssetTimeGranularity.objects.create(
            asset=test_asset,
            min_duration_minutes=60,
            any_start_time=False,
            allowed_start_times=['09:00', '12:00', '15:00', '18:00']
        )
        
        from datetime import datetime
        valid_time = datetime.strptime('09:00', '%H:%M').time()
        invalid_time = datetime.strptime('10:30', '%H:%M').time()
        
        is_valid_valid, _ = granularity.validate_start_time(valid_time)
        assert is_valid_valid is True
        
        is_valid_invalid, _ = granularity.validate_start_time(invalid_time)
        assert is_valid_invalid is False


class TestAssetLikeModel:
    """Tests for the AssetLike model."""
    
    def test_like_asset(self, db, test_user, test_asset):
        """Test liking an asset."""
        like = AssetLike.objects.create(
            asset=test_asset,
            user=test_user
        )
        assert like.asset == test_asset
        assert like.user == test_user
    
    def test_asset_like_count(self, db, test_asset, test_user, second_user):
        """Test asset like count."""
        AssetLike.objects.create(asset=test_asset, user=test_user)
        AssetLike.objects.create(asset=test_asset, user=second_user)
        
        assert test_asset.likes.count() == 2

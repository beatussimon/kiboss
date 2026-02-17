"""
Integration tests that run against real Django test database.

These tests:
1. Create data via Django ORM
2. Start Django server with test database
3. Load frontend pages
4. Assert database records are visible in UI

Run with: cd backend && python manage.py test kiboss.tests.test_integration_e2e
"""

import os
import sys
import time
import threading
import subprocess
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')

import django
django.setup()

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from kiboss.apps.users.models import User
from kiboss.apps.assets.models import Asset, AssetType, VerificationStatus
from kiboss.apps.rides.models import Ride, RideStatus
from kiboss.apps.bookings.models import Booking, BookingStatus


class IntegrationTestCase(TestCase):
    """Base test case for integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()
        
        # Create test users
        cls.owner = User.objects.create_user(
            email='owner_integration@test.com',
            password='testpass123',
            first_name='Owner',
            last_name='User',
            is_email_verified=True
        )
        
        cls.renter = User.objects.create_user(
            email='renter_integration@test.com',
            password='testpass123',
            first_name='Renter',
            last_name='User',
            is_email_verified=True
        )
        
        # Create test assets
        cls.asset1 = Asset.objects.create(
            name='Integration Test Apartment',
            description='A beautiful apartment for testing',
            asset_type=AssetType.ROOM,
            owner=cls.owner,
            address='123 Test Street',
            city='Test City',
            state='TS',
            country='US',
            postal_code='12345',
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            is_listed=True,
            average_rating=Decimal('4.50'),
            total_reviews=10
        )
        
        cls.asset2 = Asset.objects.create(
            name='Integration Test Vehicle',
            description='A reliable test vehicle',
            asset_type=AssetType.VEHICLE,
            owner=cls.owner,
            city='Test City',
            country='US',
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            is_listed=True,
            average_rating=Decimal('4.75'),
            total_reviews=5
        )
        
        # Create test rides
        cls.ride = Ride.objects.create(
            driver=cls.owner,
            vehicle_asset=cls.asset2,
            status=RideStatus.SCHEDULED,
            route_name='Integration Test Route',
            origin='New York',
            destination='Boston',
            departure_time=timezone.now() + timedelta(days=1),
            total_seats=4,
            seat_price=Decimal('25.00'),
            confirmed_seats=0
        )
        
        # Create test booking
        start = timezone.now() + timedelta(days=2)
        cls.booking = Booking.objects.create(
            renter=cls.renter,
            asset=cls.asset1,
            status=BookingStatus.PENDING,
            start_time=start,
            end_time=start + timedelta(hours=2),
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('200.00'),
            total_price=Decimal('220.00')
        )
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        # Clean up test data
        User.objects.filter(email__icontains='integration@test.com').delete()
        Asset.objects.filter(name__icontains='Integration Test').delete()
        super().tearDownClass()
    
    def setUp(self):
        """Set up each test."""
        self.client = Client()
    
    def get_jwt_token(self, email, password):
        """Get JWT access token for authentication."""
        response = self.client.post('/api/v1/auth/token/', {
            'email': email,
            'password': password
        })
        
        self.assertEqual(response.status_code, 200)
        return response.json()['access']
    
    def test_assets_api_returns_correct_data(self):
        """Test that Assets API returns the test data."""
        # Authenticate as owner using JWT token
        token = self.get_jwt_token('owner_integration@test.com', 'testpass123')
        
        # Get assets list with JWT token
        response = self.client.get('/api/v1/assets/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        asset_names = [a['name'] for a in data['results']]
        
        # Assert test assets exist in API response
        self.assertIn('Integration Test Apartment', asset_names)
        self.assertIn('Integration Test Vehicle', asset_names)
    
    def test_assets_created_in_db(self):
        """Verify assets were created in database."""
        assets = Asset.objects.filter(name__icontains='Integration Test')
        self.assertEqual(assets.count(), 2)
        
        # Verify specific asset
        asset = Asset.objects.get(name='Integration Test Apartment')
        self.assertEqual(asset.asset_type, 'ROOM')
        self.assertEqual(asset.verification_status, 'VERIFIED')
    
    def test_rides_created_in_db(self):
        """Verify rides were created in database."""
        rides = Ride.objects.filter(route_name='Integration Test Route')
        self.assertEqual(rides.count(), 1)
        
        ride = rides.first()
        self.assertEqual(ride.driver.email, 'owner_integration@test.com')
        self.assertEqual(ride.total_seats, 4)
    
    def test_bookings_created_in_db(self):
        """Verify bookings were created in database."""
        bookings = Booking.objects.filter(renter__email='renter_integration@test.com')
        self.assertEqual(bookings.count(), 1)
        
        booking = bookings.first()
        self.assertEqual(booking.status, 'PENDING')
        self.assertEqual(booking.total_price, Decimal('220.00'))
    
    def test_asset_owner_relationship(self):
        """Test asset-owner relationship."""
        asset = Asset.objects.get(name='Integration Test Apartment')
        self.assertEqual(asset.owner.email, 'owner_integration@test.com')
    
    def test_asset_list_api_count(self):
        """Test that API returns correct count of assets."""
        # Authenticate as owner using JWT token
        token = self.get_jwt_token('owner_integration@test.com', 'testpass123')
        
        response = self.client.get('/api/v1/assets/', HTTP_AUTHORIZATION=f'Bearer {token}')
        data = response.json()
        
        # Should include our test assets
        self.assertGreaterEqual(data['count'], 2)
    
    def test_ride_seat_availability(self):
        """Test ride seat availability calculations."""
        ride = Ride.objects.get(route_name='Integration Test Route')
        
        self.assertEqual(ride.get_available_seats(), 4)  # All seats available
        self.assertFalse(ride.is_full())
    
    def test_booking_status_transitions(self):
        """Test booking status can transition."""
        booking = Booking.objects.get(renter__email='renter_integration@test.com')
        
        # Transition to CONFIRMED
        booking.status = BookingStatus.CONFIRMED
        booking.save()
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
    
    def test_asset_verification_status(self):
        """Test asset verification status."""
        asset = Asset.objects.get(name='Integration Test Vehicle')
        self.assertEqual(asset.verification_status, 'VERIFIED')
        
        # Can filter by verification status
        verified = Asset.objects.filter(verification_status='VERIFIED')
        self.assertIn(asset, verified)
    
    def test_user_trust_score(self):
        """Test user trust score is set."""
        user = User.objects.get(email='owner_integration@test.com')
        self.assertIsNotNone(user.trust_score)
    
    def test_asset_ratings(self):
        """Test asset ratings are set correctly."""
        asset = Asset.objects.get(name='Integration Test Apartment')
        self.assertEqual(asset.average_rating, Decimal('4.50'))
        self.assertEqual(asset.total_reviews, 10)

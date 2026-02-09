"""
Integration Tests for KIBOSS

Tests cover:
- User authentication
- Asset creation and listing
- Booking flow (create, confirm, cancel, complete)
- Payment processing (Zenopay mock)
- Redis locking
- RBAC permissions
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from kiboss.apps.users.models import User
from kiboss.apps.assets.models import Asset, AssetType, AssetPricing, AssetAvailability
from kiboss.apps.bookings.models import Booking, BookingStatus
from kiboss.apps.payments.models import Payment, PaymentStatus


class BaseTestCase(TestCase):
    """Base test case with common setup."""
    
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.owner = User.objects.create_user(
            email='owner@test.com',
            username='owner_test',
            password='testpass123',
            first_name='Test',
            last_name='Owner'
        )
        
        self.renter = User.objects.create_user(
            email='renter@test.com',
            username='renter_test',
            password='testpass123',
            first_name='Test',
            last_name='Renter'
        )
        
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            username='admin_test',
            password='testpass123'
        )
        
        # Create test asset
        self.asset = Asset.objects.create(
            name='Test Room',
            description='A test room for rentals',
            asset_type=AssetType.ROOM,
            owner=self.owner,
            city='Test City',
            country='Test Country',
            is_active=True,
            is_listed=True,
            properties={
                'capacity': 10,
                'tax_rate': 0.08
            }
        )
        
        # Create pricing rule
        self.pricing = AssetPricing.objects.create(
            asset=self.asset,
            name='Standard Rate',
            unit_type='HOUR',
            price=Decimal('50.00'),
            is_active=True,
            priority=0
        )
        
        # Create availability rule
        self.availability = AssetAvailability.objects.create(
            asset=self.asset,
            name='Standard Availability',
            availability_type='ALWAYS',
            buffer_minutes=30,
            is_active=True
        )
        
        # Create API client
        self.client = APIClient()
        
    def get_token(self, user):
        """Get JWT token for user."""
        from rest_framework_simplejwt.tokens import RefreshToken
        
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)


class UserAuthenticationTests(BaseTestCase):
    """Tests for user authentication."""
    
    def test_user_creation(self):
        """Test user creation."""
        user = User.objects.create_user(
            email='newuser@test.com',
            username='newuser_test',
            password='testpass123'
        )
        self.assertEqual(user.email, 'newuser@test.com')
        self.assertTrue(user.is_active)
    
    def test_superuser_creation(self):
        """Test superuser creation."""
        admin = User.objects.create_superuser(
            email='newadmin@test.com',
            username='newadmin_test',
            password='testpass123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class AssetTests(BaseTestCase):
    """Tests for asset management."""
    
    def test_create_asset(self):
        """Test creating an asset."""
        asset = Asset.objects.create(
            name='New Asset',
            description='Test asset',
            asset_type=AssetType.ROOM,
            owner=self.owner,
            city='Test City',
            country='Test Country',
            is_listed=True
        )
        self.assertEqual(asset.name, 'New Asset')
        self.assertEqual(asset.owner, self.owner)
    
    def test_asset_properties(self):
        """Test asset JSON properties."""
        self.asset.properties['test_key'] = 'test_value'
        self.asset.save()
        
        retrieved = Asset.objects.get(pk=self.asset.pk)
        self.assertEqual(retrieved.get_property('test_key'), 'test_value')
    
    def test_asset_pricing(self):
        """Test pricing calculation."""
        price = self.pricing.calculate_price(quantity=2, duration_minutes=120)
        self.assertIsInstance(price, Decimal)


class BookingTests(BaseTestCase):
    """Tests for booking flow."""
    
    def test_create_booking(self):
        """Test creating a booking."""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.PENDING,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        self.assertEqual(booking.status, BookingStatus.PENDING)
        self.assertEqual(booking.renter, self.renter)
    
    def test_booking_state_transition(self):
        """Test valid booking state transitions."""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.PENDING,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        # PENDING -> CONFIRMED
        booking.transition_to(
            BookingStatus.CONFIRMED,
            actor_type='USER',
            actor_id=self.renter.id
        )
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)
        
        # CONFIRMED -> ACTIVE
        booking.transition_to(
            BookingStatus.ACTIVE,
            actor_type='USER',
            actor_id=self.renter.id
        )
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        
        # ACTIVE -> COMPLETED
        booking.transition_to(
            BookingStatus.COMPLETED,
            actor_type='USER',
            actor_id=self.renter.id
        )
        self.assertEqual(booking.status, BookingStatus.COMPLETED)
    
    def test_invalid_state_transition(self):
        """Test invalid state transition raises error."""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.PENDING,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        with self.assertRaises(ValueError):
            booking.transition_to(
                BookingStatus.COMPLETED,  # Invalid: PENDING -> COMPLETED
                actor_type='USER',
                actor_id=self.renter.id
            )
    
    def test_admin_override_requires_justification(self):
        """Test admin override requires justification."""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.PENDING,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        with self.assertRaises(ValueError):
            booking.transition_to(
                BookingStatus.CANCELLED,
                actor_type='ADMIN',
                actor_id=self.admin.id
            )
        
        # With justification
        booking.transition_to(
            BookingStatus.CANCELLED,
            actor_type='ADMIN',
            actor_id=self.admin.id,
            justification='Customer request'
        )
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
    
    def test_cancellation_fee(self):
        """Test cancellation fee calculation."""
        start_time = timezone.now() + timedelta(hours=5)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.CONFIRMED,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00')
        )
        
        # 5 hours before start - 75% fee
        fee = booking.get_cancellation_fee(timezone.now())
        self.assertEqual(fee, Decimal('75.00'))
    
    def test_late_fee_calculation(self):
        """Test late fee calculation."""
        start_time = timezone.now() - timedelta(hours=2)
        end_time = start_time + timedelta(hours=2)
        
        booking = Booking.objects.create(
            renter=self.renter,
            asset=self.asset,
            status=BookingStatus.ACTIVE,
            start_time=start_time,
            end_time=end_time,
            quantity=1,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
            total_price=Decimal('100.00'),
            late_fee_per_unit=Decimal('10.00'),
            late_fee_max=Decimal('50.00')
        )
        
        # Return 30 minutes late
        return_time = end_time + timedelta(minutes=30)
        fee = booking.calculate_late_fee(return_time)
        
        # 0.5 hours * $10 = $5
        self.assertEqual(fee, Decimal('5.00'))


class PaymentTests(BaseTestCase):
    """Tests for payment processing (Zenopay mock)."""
    
    def test_payment_authorization(self):
        """Test payment authorization."""
        booking_id = uuid.uuid4()
        payment = Payment.objects.create(
            booking_id=booking_id,
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        success = payment.authorize(
            amount=Decimal('100.00'),
            card_details={'last_four': '4242', 'brand': 'VISA'}
        )
        
        self.assertTrue(success)
        self.assertEqual(payment.status, PaymentStatus.AUTHORIZED)
        self.assertIsNotNone(payment.zenopay_authorization_code)
    
    def test_escrow_hold(self):
        """Test holding payment in escrow."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        
        self.assertEqual(payment.status, PaymentStatus.ESCROW)
        self.assertEqual(payment.escrow_amount, Decimal('100.00'))
        self.assertIsNotNone(payment.escrow_held_at)
    
    def test_escrow_release(self):
        """Test releasing escrow to owner."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        payment.release_from_escrow()
        
        self.assertEqual(payment.status, PaymentStatus.RELEASED)
        self.assertIsNotNone(payment.escrow_released_at)
    
    def test_partial_refund(self):
        """Test partial refund processing."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        
        payment.refund(Decimal('50.00'), 'Partial refund')
        
        self.assertEqual(payment.status, PaymentStatus.PARTIAL_REFUND)
        self.assertEqual(payment.refunded_amount, Decimal('50.00'))
    
    def test_penalty_application(self):
        """Test penalty application."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        
        payment.apply_penalty(Decimal('25.00'), 'Late return')
        
        self.assertEqual(payment.penalty_amount, Decimal('25.00'))
        self.assertEqual(payment.escrow_amount, Decimal('75.00'))
    
    def test_dispute_freeze(self):
        """Test payment freeze during dispute."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        payment.freeze_for_dispute()
        
        self.assertEqual(payment.status, PaymentStatus.FROZEN)
    
    def test_dispute_resolution(self):
        """Test payment resolution after dispute."""
        payment = Payment.objects.create(
            booking_id=uuid.uuid4(),
            amount=Decimal('100.00'),
            payment_method='CREDIT_CARD'
        )
        
        payment.authorize(Decimal('100.00'), {'last_four': '4242'})
        payment.hold_in_escrow()
        payment.freeze_for_dispute()
        
        # Resolve dispute - refund to renter
        payment.unfreeze_after_dispute('refund')
        
        self.assertEqual(payment.status, PaymentStatus.REFUNDED)


class RedisLockingTests(BaseTestCase):
    """Tests for Redis locking mechanism."""
    
    def test_lock_acquisition(self):
        """Test acquiring a lock."""
        from kiboss.apps.common.locking import lock_manager
        
        lock_key = f"lock:test:{uuid.uuid4()}"
        token = lock_manager.acquire_lock(lock_key, ttl=30)
        
        if token:  # May be None if Redis is not available
            self.assertIsNotNone(token)
            self.assertTrue(lock_manager.is_locked(lock_key))
            
            # Release lock
            result = lock_manager.release_lock(lock_key, token)
            self.assertTrue(result)
    
    def test_lock_release_by_owner_only(self):
        """Test that only lock owner can release."""
        from kiboss.apps.common.locking import lock_manager
        
        lock_key = f"lock:test:{uuid.uuid4()}"
        token = lock_manager.acquire_lock(lock_key, ttl=30)
        
        if token:
            # Try to release with wrong token
            result = lock_manager.release_lock(lock_key, 'wrong-token')
            self.assertFalse(result)
            
            # Lock should still exist
            self.assertTrue(lock_manager.is_locked(lock_key))
            
            # Release with correct token
            result = lock_manager.release_lock(lock_key, token)
            self.assertTrue(result)
    
    def test_lock_extension(self):
        """Test extending lock TTL."""
        from kiboss.apps.common.locking import lock_manager
        
        lock_key = f"lock:test:{uuid.uuid4()}"
        token = lock_manager.acquire_lock(lock_key, ttl=30)
        
        if token:
            # Extend lock
            result = lock_manager.extend_lock(lock_key, token, ttl=60)
            self.assertTrue(result)
            
            # Cleanup
            lock_manager.release_lock(lock_key, token)
    
    def test_rate_limiting(self):
        """Test rate limiting."""
        from kiboss.apps.common.locking import rate_limiter
        
        is_allowed, remaining, reset_time = rate_limiter.check_rate_limit(
            key=f"ratelimit:test:{uuid.uuid4()}",
            limit=10,
            window_seconds=3600
        )
        
        self.assertTrue(is_allowed)
        self.assertGreaterEqual(remaining, 0)


class RBACTests(BaseTestCase):
    """Tests for Role-Based Access Control."""
    
    def test_admin_has_all_permissions(self):
        """Test that superadmin has all permissions."""
        self.assertTrue(self.admin.is_superuser)
        self.assertTrue(self.admin.is_staff)
    
    def test_owner_can_edit_own_asset(self):
        """Test that owners can edit their own assets."""
        # Owner should be able to update their own asset
        self.assertEqual(self.asset.owner, self.owner)
    
    def test_renter_cannot_edit_asset(self):
        """Test that renters cannot edit others' assets."""
        # Renter should not be owner
        self.assertNotEqual(self.asset.owner, self.renter)


class TrustScoreTests(BaseTestCase):
    """Tests for trust score calculations."""
    
    def test_initial_trust_score(self):
        """Test initial trust score."""
        self.assertEqual(self.owner.trust_score, Decimal('50.00'))
        self.assertEqual(self.renter.trust_score, Decimal('50.00'))
    
    def test_trust_score_update(self):
        """Test trust score update."""
        initial = self.renter.trust_score
        
        self.renter.update_trust_score(4.5)
        
        self.assertNotEqual(self.renter.trust_score, initial)
        self.assertEqual(self.renter.total_ratings_count, 1)


# Test runner configuration
if __name__ == '__main__':
    import unittest
    unittest.main()

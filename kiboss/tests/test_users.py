"""
Unit tests for User models.

Tests cover:
- User creation and validation
- Trust score updates
- Profile management
- Device management
- JWT token blacklisting
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from kiboss.apps.users.models import User, UserProfile, TrustScore, Device, BlacklistedToken


class TestUserModel:
    """Tests for the User model."""
    
    def test_create_user_with_email(self, db):
        """Test creating a user with email."""
        user = User.objects.create_user(
            email='newuser@example.com',
            password='testpass123'
        )
        assert user.email == 'newuser@example.com'
        assert user.check_password('testpass123')
        assert user.username is None
        assert user.is_active is True
        assert user.is_email_verified is False
    
    def test_create_user_without_email_raises_error(self, db):
        """Test that creating a user without email raises ValueError."""
        with pytest.raises(ValueError, match='The Email field must be set'):
            User.objects.create_user(email='', password='testpass123')
    
    def test_create_superuser(self, db):
        """Test creating a superuser."""
        superuser = User.objects.create_superuser(
            email='superuser@example.com',
            password='adminpass123'
        )
        assert superuser.is_staff is True
        assert superuser.is_superuser is True
        assert superuser.is_active is True
    
    def test_superuser_requires_staff(self, db):
        """Test that superuser must have is_staff=True."""
        with pytest.raises(ValueError, match='Superuser must have is_staff=True'):
            User.objects.create_superuser(
                email='superuser@example.com',
                password='adminpass123',
                is_staff=False
            )
    
    def test_get_full_name(self, db):
        """Test getting user's full name."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        assert user.get_full_name() == 'John Doe'
    
    def test_get_full_name_empty_returns_email(self, db):
        """Test that empty name returns email."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        assert user.get_full_name() == 'test@example.com'
    
    def test_update_trust_score_first_rating(self, db):
        """Test updating trust score with first rating."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.update_trust_score(4.5)
        user.refresh_from_db()
        
        assert user.trust_score == Decimal('4.50')
        assert user.total_ratings_count == 1
    
    def test_update_trust_score_weighted_average(self, db):
        """Test that trust score uses weighted average."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            trust_score=Decimal('80.00'),
            total_ratings_count=5
        )
        user.update_trust_score(4.0)
        user.refresh_from_db()
        
        # Expected: 0.7 * 80 + 0.3 * 4 = 56 + 1.2 = 57.2
        expected = (Decimal('80.00') * Decimal('0.7')) + (Decimal('4.0') * Decimal('0.3'))
        assert user.trust_score == expected
        assert user.total_ratings_count == 6
    
    def test_is_verified_property(self, db):
        """Test is_verified property."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_email_verified=True,
            is_phone_verified=False
        )
        assert user.is_verified is False
        
        user.is_phone_verified = True
        user.save()
        assert user.is_verified is True
    
    def test_user_string_representation(self, db):
        """Test user's string representation."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        assert str(user) == 'test@example.com'


class TestUserProfileModel:
    """Tests for the UserProfile model."""
    
    def test_create_profile(self, db, test_user):
        """Test creating a user profile."""
        profile = UserProfile.objects.create(
            user=test_user,
            phone='+1234567890',
            city='Test City',
            country='US',
            bio='Test bio'
        )
        assert profile.user == test_user
        assert profile.phone == '+1234567890'
        assert str(profile) == f'Profile for {test_user.email}'
    
    def test_get_notification_preference(self, db, test_user):
        """Test getting notification preferences."""
        profile = UserProfile.objects.create(
            user=test_user,
            notification_settings={
                'email': True,
                'sms': False,
                'push': True
            }
        )
        assert profile.get_notification_preference('email') is True
        assert profile.get_notification_preference('sms') is False
        assert profile.get_notification_preference('unknown') is True  # default


class TestTrustScoreModel:
    """Tests for the TrustScore model."""
    
    def test_calculate_overall_score(self, db, test_user):
        """Test calculating overall trust score."""
        trust = TrustScore.objects.create(
            user=test_user,
            reliability_score=Decimal('80.00'),
            communication_score=Decimal('90.00'),
            cleanliness_score=Decimal('85.00'),
            timeliness_score=Decimal('75.00')
        )
        trust.calculate_overall_score()
        trust.refresh_from_db()
        
        # Expected: 0.25*80 + 0.25*90 + 0.2*85 + 0.3*75 = 20 + 22.5 + 17 + 22.5 = 82
        expected = (
            Decimal('80.00') * Decimal('0.25') +
            Decimal('90.00') * Decimal('0.25') +
            Decimal('85.00') * Decimal('0.2') +
            Decimal('75.00') * Decimal('0.3')
        )
        assert trust.overall_score == expected
    
    def test_update_from_rating_reliability(self, db, test_user):
        """Test updating reliability score from rating."""
        trust = TrustScore.objects.create(
            user=test_user,
            reliability_score=Decimal('50.00')
        )
        trust.update_from_rating('reliability', 4.0)
        trust.refresh_from_db()
        
        expected = (Decimal('50.00') * Decimal('0.7')) + (Decimal('4.0') * Decimal('0.3'))
        assert trust.reliability_score == expected
    
    def test_update_from_invalid_rating_type(self, db, test_user):
        """Test updating with invalid rating type doesn't change scores."""
        trust = TrustScore.objects.create(
            user=test_user,
            reliability_score=Decimal('80.00')
        )
        original_score = trust.reliability_score
        trust.update_from_rating('invalid', 4.0)
        
        assert trust.reliability_score == original_score


class TestDeviceModel:
    """Tests for the Device model."""
    
    def test_create_device(self, db, test_user):
        """Test creating a device."""
        device = Device.objects.create(
            user=test_user,
            device_type='ios',
            device_token='test_token_123',
            device_name='iPhone 12'
        )
        assert device.user == test_user
        assert device.is_active is True
        assert str(device) == 'iPhone 12'
    
    def test_mark_active(self, db, test_user):
        """Test marking device as active."""
        device = Device.objects.create(
            user=test_user,
            device_type='android',
            device_token='token123'
        )
        old_active = device.last_active_at
        device.mark_active()
        
        assert device.last_active_at >= old_active


class TestBlacklistedTokenModel:
    """Tests for the BlacklistedToken model."""
    
    def test_blacklist_token(self, db, test_user):
        """Test blacklisting a token."""
        token = BlacklistedToken.objects.create(
            token='test_jwt_token',
            user=test_user,
            expires_at=timezone.now() + timedelta(days=1)
        )
        assert BlacklistedToken.is_blacklisted('test_jwt_token') is True
        assert BlacklistedToken.is_blacklisted('other_token') is False
    
    def test_expired_token_not_blacklisted(self, db, test_user):
        """Test that expired tokens are not considered blacklisted."""
        BlacklistedToken.objects.create(
            token='expired_token',
            user=test_user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        assert BlacklistedToken.is_blacklisted('expired_token') is False

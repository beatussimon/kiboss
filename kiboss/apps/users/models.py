"""
User Models for KIBOSS

This module contains all user-related models including:
- User (authentication)
- Profile (extended user data)
- TrustScore (calculated trust metrics)
- Device (for push notifications)
"""

import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.utils import timezone


# Default values using Decimal
DEFAULT_TRUST_SCORE = Decimal('50.00')
DEFAULT_OVERALL_SCORE = Decimal('50.00')


class VerificationTier:
    """Verification tier constants for user verification levels."""
    NONE = 'none'
    BASIC = 'basic'
    PREMIUM = 'premium'
    GOLD = 'gold'
    BUSINESS = 'business'
    
    CHOICES = [
        (NONE, 'None'),
        (BASIC, 'Basic'),
        (PREMIUM, 'Premium'),
        (GOLD, 'Gold'),
        (BUSINESS, 'Business'),
    ]
    
    # Tier thresholds
    GOLD_THRESHOLD = 95.0  # Trust score threshold for gold
    PREMIUM_THRESHOLD = 80.0  # Trust score threshold for premium
    BASIC_THRESHOLD = 50.0  # Trust score threshold for basic
    
    @classmethod
    def get_tier(cls, trust_score):
        """Get verification tier based on trust score."""
        # Note: BUSINESS tier is manually assigned via corporate verification
        score = float(trust_score) if trust_score else 0
        if score >= cls.GOLD_THRESHOLD:
            return cls.GOLD
        elif score >= cls.PREMIUM_THRESHOLD:
            return cls.PREMIUM
        elif score >= cls.BASIC_THRESHOLD:
            return cls.BASIC
        return cls.NONE
    
    @classmethod
    def get_badge_color(cls, tier):
        """Get badge color for verification tier."""
        colors = {
            cls.GOLD: 'gold',
            cls.BUSINESS: 'indigo',
            cls.PREMIUM: 'blue',
            cls.BASIC: 'gray',
            cls.NONE: None
        }
        return colors.get(tier)


class UserManager(BaseUserManager):
    """Custom user manager for User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError('The Email field must be set')

        # Backward compatibility: legacy callers may still pass username.
        extra_fields.pop('username', None)
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser."""
        if email is None:
            raise ValueError('Email field must be set')
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)


class UserQuerySet(models.QuerySet):
    """Custom queryset to handle safe cleanup of related protected records."""

    def delete(self, *args, **kwargs):
        from kiboss.apps.bookings.models import Booking
        from kiboss.apps.rides.models import Ride, SeatBooking, RideSchedule
        from kiboss.apps.payments.models import Payment, Dispute

        for user in self:
            SeatBooking.objects.filter(passenger=user).delete()
            RideSchedule.objects.filter(driver=user).delete()
            Ride.objects.filter(driver=user).delete()

            impacted_bookings = Booking.objects.filter(models.Q(renter=user) | models.Q(asset__owner=user))
            Dispute.objects.filter(booking__in=impacted_bookings).delete()
            Payment.objects.filter(booking__in=impacted_bookings).delete()
            impacted_bookings.delete()

        return super().delete(*args, **kwargs)


class User(AbstractUser):
    """
    Custom User model for KIBOSS.
    
    Uses email as the primary identifier instead of username.
    Supports RBAC with role-based permissions.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = None
    
    # Custom manager
    objects = UserManager()
    
    # Verification status
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    is_identity_verified = models.BooleanField(default=False)
    
    # Verification tier (manual override for special users)
    verification_tier = models.CharField(
        max_length=20,
        choices=VerificationTier.CHOICES,
        default=VerificationTier.NONE
    )
    
    # Trust and reputation
    trust_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_TRUST_SCORE)
    total_ratings_count = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['trust_score']),
        ]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def update_trust_score(self, new_rating):
        """
        Update trust score based on new rating.
        Uses weighted average with decay factor.
        """
        if self.total_ratings_count == 0:
            self.trust_score = Decimal(str(new_rating))
        else:
            # Weighted average: 70% old score, 30% new rating
            self.trust_score = (self.trust_score * Decimal('0.7')) + (Decimal(str(new_rating)) * Decimal('0.3'))
        
        self.total_ratings_count += 1
        self.save(update_fields=['trust_score', 'total_ratings_count', 'updated_at'])
    
    @property
    def is_verified(self):
        """Check if user meets verification threshold."""
        return self.is_email_verified and self.is_phone_verified
    
    @property
    def verification_badge(self):
        """Get the verification badge info for this user."""
        # If manual tier is set, use it
        if self.verification_tier and self.verification_tier != VerificationTier.NONE:
            return {
                'tier': self.verification_tier,
                'color': VerificationTier.get_badge_color(self.verification_tier)
            }
        # Otherwise calculate from trust score
        tier = VerificationTier.get_tier(self.trust_score)
        return {
            'tier': tier,
            'color': VerificationTier.get_badge_color(tier)
        }
    
    @property
    def has_verification_badge(self):
        """Check if user has any verification badge."""
        return self.verification_badge['color'] is not None


class UserProfileManager(models.Manager):
    """Idempotent create for one-to-one profile records."""

    def create(self, **kwargs):
        user = kwargs.get('user')
        if user is None:
            return super().create(**kwargs)
        defaults = {k: v for k, v in kwargs.items() if k != 'user'}
        profile, _ = self.get_or_create(user=user, defaults=defaults)
        for field, value in kwargs.items():
            if field != 'user':
                setattr(profile, field, value)
        profile.save()
        return profile


class UserProfile(models.Model):
    """
    Extended user profile with additional information.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Personal information
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Location
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Tanzania', blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    currency = models.CharField(max_length=3, default='TZS')
    
    # Notification preferences (JSON)
    notification_settings = models.JSONField(default=dict, blank=True)
    
    # Statistics
    total_bookings = models.IntegerField(default=0)
    total_listings = models.IntegerField(default=0)
    total_rides_as_driver = models.IntegerField(default=0)
    total_rides_as_passenger = models.IntegerField(default=0)
    
    # Verification documents
    identity_document = models.FileField(upload_to='identity/', blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserProfileManager()
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.email}"
    
    def get_notification_preference(self, notification_type):
        """Get user's preference for a specific notification type."""
        return self.notification_settings.get(notification_type, True)


class TrustScoreManager(models.Manager):
    """Idempotent create for one-to-one trust records."""

    def create(self, **kwargs):
        user = kwargs.get('user')
        if user is None:
            return super().create(**kwargs)
        defaults = {k: v for k, v in kwargs.items() if k != 'user'}
        trust, _ = self.get_or_create(user=user, defaults=defaults)
        for field, value in kwargs.items():
            if field != 'user':
                setattr(trust, field, value)
        trust.save()
        return trust


class TrustScore(models.Model):
    """
    Detailed trust score breakdown.
    Tracks different aspects of user trustworthiness.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='trust_score_info'
    )
    
    # Score components (0-100 each)
    reliability_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_OVERALL_SCORE)
    communication_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_OVERALL_SCORE)
    cleanliness_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_OVERALL_SCORE)
    timeliness_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_OVERALL_SCORE)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_OVERALL_SCORE)
    
    # Counts
    completed_bookings = models.IntegerField(default=0)
    cancelled_bookings = models.IntegerField(default=0)
    no_shows = models.IntegerField(default=0)
    late_returns = models.IntegerField(default=0)
    disputes_initiated = models.IntegerField(default=0)
    disputes_against = models.IntegerField(default=0)
    
    # Badges and achievements
    badges = models.JSONField(default=list, blank=True)
    
    # Timestamps
    last_calculated = models.DateTimeField(auto_now=True)

    objects = TrustScoreManager()
    
    class Meta:
        db_table = 'trust_scores'
        verbose_name = 'Trust Score'
        verbose_name_plural = 'Trust Scores'
    
    def __str__(self):
        return f"Trust details for {self.user.email}"
    
    def calculate_overall_score(self):
        """Calculate overall score from components."""
        self.overall_score = (
            self.reliability_score * Decimal('0.25') +
            self.communication_score * Decimal('0.25') +
            self.cleanliness_score * Decimal('0.2') +
            self.timeliness_score * Decimal('0.3')
        )
        self.save(update_fields=['overall_score', 'last_calculated'])
    
    def update_from_rating(self, rating_type, score):
        """Update specific score component from a rating."""
        updated_fields = []
        if rating_type == 'reliability':
            self.reliability_score = self._update_component(self.reliability_score, score)
            updated_fields.append('reliability_score')
        elif rating_type == 'communication':
            self.communication_score = self._update_component(self.communication_score, score)
            updated_fields.append('communication_score')
        elif rating_type == 'cleanliness':
            self.cleanliness_score = self._update_component(self.cleanliness_score, score)
            updated_fields.append('cleanliness_score')
        elif rating_type == 'timeliness':
            self.timeliness_score = self._update_component(self.timeliness_score, score)
            updated_fields.append('timeliness_score')

        if updated_fields:
            self.save(update_fields=updated_fields + ['last_calculated'])
        self.calculate_overall_score()
    
    def _update_component(self, current, new_score):
        """Update a score component with decay factor."""
        new_decimal = Decimal(str(new_score))
        return (current * Decimal('0.7')) + (new_decimal * Decimal('0.3'))


class Device(models.Model):
    """
    User devices for push notifications.
    """
    
    DEVICE_TYPES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='devices'
    )
    
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_token = models.CharField(max_length=255)
    device_name = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(default=timezone.now)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'devices'
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        unique_together = ['user', 'device_token']
    
    def __str__(self):
        return self.device_name or self.device_token[:20]
    
    def mark_active(self):
        """Mark device as recently active."""
        self.last_active_at = timezone.now()
        self.save(update_fields=['last_active_at', 'updated_at'])


class BlacklistedToken(models.Model):
    """
    JWT tokens that have been blacklisted (logout or token refresh).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=500, unique=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blacklisted_tokens'
    )
    reason = models.CharField(max_length=100, default='logout')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'blacklisted_tokens'
        verbose_name = 'Blacklisted Token'
        verbose_name_plural = 'Blacklisted Tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Blacklisted token for {self.user.email}"
    
    @classmethod
    def is_blacklisted(cls, token):
        """Check if a token is blacklisted."""
        from django.utils import timezone as tz
        return cls.objects.filter(token=token, expires_at__gt=tz.now()).exists()


class CorporateProfile(models.Model):
    """
    Corporate identity for business users.
    Linked 1:1 to User.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='corporate_profile'
    )
    
    company_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100)
    tax_id = models.CharField(max_length=100, blank=True)
    verification_documents = models.JSONField(default=list, blank=True)
    
    verification_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'corporate_profiles'
        verbose_name = 'Corporate Profile'
        verbose_name_plural = 'Corporate Profiles'

    def __str__(self):
        return f"{self.company_name} ({self.verification_status})"


class BusinessSubscription(models.Model):
    """
    Subscription tracking for Corporate/Business users.
    """
    class Plan(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly'
        YEARLY = 'YEARLY', 'Yearly'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Payment'
        ACTIVE = 'ACTIVE', 'Active'
        EXPIRED = 'EXPIRED', 'Expired'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CorporateProfile,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    
    plan_type = models.CharField(max_length=20, choices=Plan.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_proof_url = models.URLField(blank=True, help_text="Direct URL to receipt if uploaded manually")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.company_name} - {self.plan_type} ({self.status})"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE and self.end_date > timezone.now()

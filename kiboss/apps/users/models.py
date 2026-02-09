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


class UserManager(BaseUserManager):
    """Custom user manager for User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError('The Email field must be set')
        
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
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    currency = models.CharField(max_length=3, default='USD')
    
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
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.email}"
    
    def get_notification_preference(self, notification_type):
        """Get user's preference for a specific notification type."""
        return self.notification_settings.get(notification_type, True)


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
        if rating_type == 'reliability':
            self.reliability_score = self._update_component(self.reliability_score, score)
        elif rating_type == 'communication':
            self.communication_score = self._update_component(self.communication_score, score)
        elif rating_type == 'cleanliness':
            self.cleanliness_score = self._update_component(self.cleanliness_score, score)
        elif rating_type == 'timeliness':
            self.timeliness_score = self._update_component(self.timeliness_score, score)
        
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
        return f"{self.device_type} - {self.device_name or self.device_token[:20]}"
    
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

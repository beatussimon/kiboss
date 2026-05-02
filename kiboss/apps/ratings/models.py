"""
Rating Models for KIBOSS - Ratings & Trust System
"""

import uuid
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings
from django.utils import timezone


class RatingCategory(models.TextChoices):
    """Rating category enumeration."""
    RENTER_TO_OWNER = 'RENTER_TO_OWNER', 'Renter to Owner'
    OWNER_TO_RENTER = 'OWNER_TO_RENTER', 'Owner to Renter'
    DRIVER_TO_PASSENGER = 'DRIVER_TO_PASSENGER', 'Driver to Passenger'
    PASSENGER_TO_DRIVER = 'PASSENGER_TO_DRIVER', 'Passenger to Driver'


class RatingStatus(models.TextChoices):
    """Rating status."""
    SUBMITTED = 'SUBMITTED', 'Submitted'
    REVEALED = 'REVEALED', 'Mutually Revealed'
    MODERATION_PENDING = 'MODERATION_PENDING', 'Pending Moderation'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    APPEALED = 'APPEALED', 'Appealed'


# Default trust score value
DEFAULT_TRUST = Decimal('50.00')


class Rating(models.Model):
    """Rating model for transactions."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ratings'
    )
    ride = models.ForeignKey(
        'rides.SeatBooking',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='ratings'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='given_ratings'
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='received_ratings'
    )
    category = models.CharField(max_length=30, choices=RatingCategory.choices)
    
    # Scores (1-5 scale)
    overall_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    reliability_rating = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    communication_rating = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    cleanliness_rating = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    timeliness_rating = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Content
    title = models.CharField(max_length=100, blank=True)
    comment = models.TextField(max_length=2000, blank=True)
    private_feedback = models.TextField(max_length=1000, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=RatingStatus.choices,
        default=RatingStatus.SUBMITTED
    )
    is_mutually_revealed = models.BooleanField(default=False)
    revealed_at = models.DateTimeField(blank=True, null=True)
    
    # Asset rating
    asset_rating = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Moderation
    moderation_reason = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='moderated_ratings'
    )
    moderated_at = models.DateTimeField(blank=True, null=True)
    
    # Appeal
    appeal_reason = models.TextField(blank=True)
    appealed_at = models.DateTimeField(blank=True, null=True)
    appeal_response = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ratings'
        unique_together = [
            ['booking', 'reviewer'],   # One review per user per booking
            ['ride', 'reviewer'],       # One review per user per ride
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(booking__isnull=False, ride__isnull=True) |
                          models.Q(booking__isnull=True, ride__isnull=False),
                name='rating_exactly_one_source'
            )
        ]
    
    def __str__(self):
        return f"Rating {self.id}: {self.reviewer.email} -> {self.reviewee.email}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # 11. RIDE REVIEW INTEGRITY
        if self.ride:
            # Reviewer must be the passenger on this ride booking
            if self.ride.passenger != self.reviewer:
                raise ValidationError({'reviewer': "Only the actual passenger of this ride can leave a review."})
            # Ride booking must be COMPLETED
            if self.ride.status != 'COMPLETED':
                raise ValidationError({'ride': "Reviews can only be left for rides that have been COMPLETED."})
    
    def reveal_mutually(self):
        """Reveal ratings to each other."""
        self.is_mutually_revealed = True
        self.revealed_at = timezone.now()
        self.save()

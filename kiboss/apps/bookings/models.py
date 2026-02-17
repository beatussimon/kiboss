"""
Booking Models for KIBOSS - Booking Engine

This module implements the state-machine-based booking engine with:
- PENDING → CONFIRMED → ACTIVE → COMPLETED flow
- Support for CANCELLED, EXPIRED, DISPUTED states
- Redis locking for double-booking prevention
- Time overlap detection
- Grace periods and buffer times
"""

import uuid
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone


class BookingStatus(models.TextChoices):
    """
    Booking status enumeration.
    State machine transitions:
    
    PENDING → CONFIRMED (payment successful + contract accepted)
    PENDING → EXPIRED (payment timeout - Celery)
    CONFIRMED → ACTIVE (start time reached)
    CONFIRMED → EXPIRED (no-show - Celery)
    CONFIRMED → CANCELLED (user cancellation before start)
    ACTIVE → COMPLETED (end time reached + returned)
    ACTIVE → CANCELLED (early termination)
    ACTIVE → DISPUTED (issues during rental)
    COMPLETED → DISPUTED (post-rental disputes)
    """
    PENDING = 'PENDING', 'Pending'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    EXPIRED = 'EXPIRED', 'Expired'
    DISPUTED = 'DISPUTED', 'Disputed'


class BookingStatusTransition(models.Model):
    """
    Audit log for booking status transitions.
    Records every state change with timestamp and actor.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        'Booking',
        on_delete=models.CASCADE,
        related_name='status_transitions'
    )
    
    from_status = models.CharField(max_length=20, choices=BookingStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=BookingStatus.choices)
    
    # Actor information
    actor_type = models.CharField(
        max_length=20,
        choices=[
            ('USER', 'User'),
            ('SYSTEM', 'System'),
            ('ADMIN', 'Admin'),
            ('CELERY', 'Celery Task'),
        ]
    )
    actor_id = models.UUIDField(blank=True, null=True)
    
    # Reason and justification
    reason = models.TextField(blank=True)
    justification = models.TextField(blank=True, help_text="Required for admin overrides")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'booking_status_transitions'
        verbose_name = 'Booking Status Transition'
        verbose_name_plural = 'Booking Status Transitions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.booking.id}: {self.from_status} → {self.to_status} by {self.actor_type}"


class Booking(models.Model):
    """
    Core Booking model.
    
    Represents a rental transaction between a renter and asset owner.
    Implements state machine for booking lifecycle.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Parties
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rentals'
    )
    asset = models.ForeignKey(
        'assets.Asset',
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    
    # Status (state machine)
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )
    
    # Time details
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Quantity (number of units, seats, etc.)
    quantity = models.PositiveIntegerField(default=1)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    taxes = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Currency
    currency = models.CharField(max_length=3, default='USD')
    
    # Pricing breakdown (JSON for audit)
    price_breakdown = models.JSONField(default=dict, blank=True)
    
    # Contract reference
    contract = models.OneToOneField(
        'contracts.Contract',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='booking_contract'
    )
    
    # Payment reference
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='booking_payment'
    )
    
    # Grace periods and buffers
    grace_period_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Grace period for late returns (minutes)"
    )
    buffer_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Buffer time between bookings (minutes)"
    )
    
    # Late fees
    late_fee_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Late fee per unit per hour"
    )
    late_fee_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Maximum late fee"
    )
    
    # Cancellations
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cancelled_bookings'
    )
    cancellation_reason = models.TextField(blank=True)
    cancellation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Completion
    completed_at = models.DateTimeField(blank=True, null=True)
    actual_return_time = models.DateTimeField(blank=True, null=True)
    
    # Late return tracking
    is_late = models.BooleanField(default=False)
    late_minutes = models.PositiveIntegerField(default=0)
    late_fee_charged = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Dispute
    dispute = models.OneToOneField(
        'payments.Dispute',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='booking_dispute'
    )
    
    # Notes
    renter_notes = models.TextField(blank=True, help_text="Notes from renter")
    owner_notes = models.TextField(blank=True, help_text="Notes from owner")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['renter']),
            models.Index(fields=['asset']),
            models.Index(fields=['start_time']),
            models.Index(fields=['end_time']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'start_time']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='end_time_after_start_time'
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='quantity_at_least_1'
            ),
        ]
    
    def __str__(self):
        return f"Booking {self.id} - {self.renter.email} / {self.asset.name} ({self.status})"

    def save(self, *args, **kwargs):
        is_create = self._state.adding
        super().save(*args, **kwargs)
        if is_create and not self.price_breakdown:
            BookingTimeline.log_event(
                booking=self,
                event_type='CREATED',
                description='Booking created',
                actor_type='USER',
                actor_id=self.renter_id,
            )
    
    # State Machine Methods
    
    def transition_to(self, new_status, actor_type, actor_id=None, reason='', justification=''):
        """
        Perform state transition with validation and audit.
        
        Args:
            new_status: Target status
            actor_type: Who is making the change (USER, SYSTEM, ADMIN, CELERY)
            actor_id: ID of the actor (for USER/ADMIN)
            reason: Reason for transition
            justification: Required for admin overrides
            
        Returns:
            bool: Whether transition was successful
        """
        # Admin justification required for overrides
        if actor_type == 'ADMIN' and not justification:
            raise ValueError("Admin override requires justification")

        # Validate state transition for non-admin actors
        if self.status == BookingStatus.PENDING:
            current_transitions = [BookingStatus.CONFIRMED, BookingStatus.EXPIRED]
        elif self.status == BookingStatus.CONFIRMED:
            current_transitions = [BookingStatus.ACTIVE, BookingStatus.EXPIRED, 
                                   BookingStatus.CANCELLED, BookingStatus.DISPUTED]
        elif self.status == BookingStatus.ACTIVE:
            current_transitions = [BookingStatus.COMPLETED, BookingStatus.CANCELLED, 
                                   BookingStatus.DISPUTED]
        elif self.status == BookingStatus.COMPLETED:
            current_transitions = [BookingStatus.DISPUTED]
        else:
            current_transitions = []
        
        if actor_type != 'ADMIN' and new_status not in current_transitions:
            raise ValueError(
                f"Invalid transition: {self.status} → {new_status}. "
                f"Valid transitions from {self.status}: {current_transitions}"
            )
        
        old_status = self.status
        
        with transaction.atomic():
            # Create transition record
            BookingStatusTransition.objects.create(
                booking=self,
                from_status=old_status,
                to_status=new_status,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=reason,
                justification=justification
            )
            
            # Update status
            self.status = new_status
            self.updated_at = timezone.now()
            
            # Handle specific transitions
            if new_status == BookingStatus.CANCELLED:
                self.cancelled_at = timezone.now()
                self.cancelled_by_id = actor_id
                self.cancellation_reason = reason
            
            elif new_status == BookingStatus.COMPLETED:
                self.completed_at = timezone.now()
            
            self.save()

            # Log timeline for transition.
            BookingTimeline.log_event(
                booking=self,
                event_type=str(new_status),
                description=f'Booking transitioned to {new_status}',
                actor_type=actor_type,
                actor_id=actor_id,
                data={'from_status': str(old_status), 'to_status': str(new_status)},
            )

            # Keep trust score counters aligned with lifecycle.
            if new_status in [BookingStatus.CANCELLED, BookingStatus.COMPLETED]:
                from kiboss.apps.users.models import TrustScore
                trust, _ = TrustScore.objects.get_or_create(user=self.renter)
                updated_fields = []
                if new_status == BookingStatus.CANCELLED:
                    trust.cancelled_bookings += 1
                    updated_fields.append('cancelled_bookings')
                if new_status == BookingStatus.COMPLETED:
                    trust.completed_bookings += 1
                    updated_fields.append('completed_bookings')
                if updated_fields:
                    trust.save(update_fields=updated_fields + ['last_calculated'])
        
        return True
    
    def is_cancellable(self):
        """Check if booking can be cancelled."""
        if self.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
            return False, f"Cannot cancel booking in {self.status} status"
        return True, None
    
    def is_startable(self):
        """Check if booking can be started."""
        if self.status != BookingStatus.CONFIRMED:
            return False, f"Cannot start booking in {self.status} status"
        return True, None
    
    def is_completable(self):
        """Check if booking can be completed."""
        if self.status != BookingStatus.ACTIVE:
            return False, f"Cannot complete booking in {self.status} status"
        return True, None
    
    def calculate_late_fee(self, return_time):
        """Calculate late fee based on return time."""
        late_duration = return_time - self.end_time
        late_seconds = max(late_duration.total_seconds(), 0)
        if late_seconds <= 0:
            return Decimal('0.00')
        late_hours = Decimal(str(late_seconds / 3600))
        late_fee = late_hours * self.late_fee_per_unit * Decimal(str(self.quantity))

        # Escalate to max fee for significant lateness.
        if self.late_fee_max > Decimal('0.00') and late_hours >= Decimal('3'):
            return self.late_fee_max

        return min(late_fee, self.late_fee_max)
    
    def get_duration_hours(self):
        """Get booking duration in hours."""
        duration = self.end_time - self.start_time
        return duration.total_seconds() / 3600
    
    def get_cancellation_fee(self, cancel_time):
        """
        Calculate cancellation fee based on timing.
        
        Rules:
        - More than 48 hours before: 0%
        - 24-48 hours: 25%
        - 12-24 hours: 50%
        - Less than 12 hours: 75%
        - Less than 2 hours: 100%
        """
        hours_until_start = (self.start_time - cancel_time).total_seconds() / 3600
        
        if hours_until_start > 48:
            return Decimal('0.00')
        elif hours_until_start > 24:
            return self.subtotal * Decimal('0.25')
        elif hours_until_start > 12:
            return self.subtotal * Decimal('0.50')
        elif hours_until_start > 2:
            return self.subtotal * Decimal('0.75')
        else:
            return self.subtotal


class BookingTimeline(models.Model):
    """
    Detailed timeline events for bookings.
    Tracks all significant events during a booking lifecycle.
    """
    
    EVENT_TYPES = [
        ('CREATED', 'Booking Created'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('PAYMENT_CONFIRMED', 'Payment Confirmed'),
        ('CONTRACT_GENERATED', 'Contract Generated'),
        ('CONTRACT_ACCEPTED', 'Contract Accepted'),
        ('CONFIRMED', 'Booking Confirmed'),
        ('REMINDER_SENT', 'Reminder Sent'),
        ('STARTED', 'Booking Started'),
        ('EXTENDED', 'Booking Extended'),
        ('COMPLETED', 'Booking Completed'),
        ('CANCELLED', 'Booking Cancelled'),
        ('LATE_DETECTED', 'Late Return Detected'),
        ('LATE_FEE_CHARGED', 'Late Fee Charged'),
        ('DISPUTE_RAISED', 'Dispute Raised'),
        ('DISPUTE_RESOLVED', 'Dispute Resolved'),
        ('NO_SHOW', 'No Show'),
        ('EXPIRED', 'Booking Expired'),
        ('PAYMENT_REFUNDED', 'Payment Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )
    
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    description = models.TextField()
    
    # Actor
    actor_type = models.CharField(max_length=20, choices=[
        ('USER', 'User'),
        ('SYSTEM', 'System'),
        ('ADMIN', 'Admin'),
        ('CELERY', 'Celery Task'),
    ])
    actor_id = models.UUIDField(blank=True, null=True)
    
    # Data
    data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'booking_timeline'
        verbose_name = 'Booking Timeline'
        verbose_name_plural = 'Booking Timeline Events'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.booking.id} - {self.event_type} at {self.created_at}"
    
    @classmethod
    def log_event(cls, booking, event_type, description, actor_type, actor_id=None, data=None):
        """Create a timeline event."""
        return cls.objects.create(
            booking=booking,
            event_type=event_type,
            description=description,
            actor_type=actor_type,
            actor_id=actor_id,
            data=data or {}
        )


class BookingLock(models.Model):
    """
    Redis-based distributed lock for booking operations.
    Prevents race conditions and double bookings.
    """
    
    LOCK_TYPES = [
        ('AVAILABILITY', 'Availability Check'),
        ('BOOKING', 'Booking Creation'),
        ('PAYMENT', 'Payment Processing'),
        ('CANCELLATION', 'Cancellation'),
        ('COMPLETION', 'Completion'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lock_type = models.CharField(max_length=20, choices=LOCK_TYPES)
    resource_type = models.CharField(max_length=50, help_text="e.g., 'asset', 'booking'")
    resource_id = models.UUIDField()
    
    # Lock owner
    owner_id = models.UUIDField()
    owner_process = models.CharField(max_length=100, help_text="Process ID")
    
    # Lock metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    acquired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'booking_locks'
        verbose_name = 'Booking Lock'
        verbose_name_plural = 'Booking Locks'
        indexes = [
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Lock {self.lock_type} on {self.resource_type}:{self.resource_id}"


class AvailabilitySlot(models.Model):
    """
    Pre-calculated availability slots for assets.
    Used for efficient availability queries.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        'assets.Asset',
        on_delete=models.CASCADE,
        related_name='availability_slots'
    )
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    is_available = models.BooleanField(default=True)
    capacity = models.PositiveIntegerField(default=1)
    booked_quantity = models.PositiveIntegerField(default=0)
    
    # Cached data
    cache_version = models.PositiveIntegerField(default=1)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'availability_slots'
        verbose_name = 'Availability Slot'
        verbose_name_plural = 'Availability Slots'
        indexes = [
            models.Index(fields=['asset', 'start_time', 'end_time']),
            models.Index(fields=['asset', 'is_available']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(booked_quantity__lte=models.F('capacity')),
                name='booked_not_exceed_capacity'
            ),
        ]
    
    def __str__(self):
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.asset.name}: {self.start_time} - {self.end_time} ({status})"
    
    def get_available_quantity(self):
        """Get remaining available quantity."""
        return max(0, self.capacity - self.booked_quantity)
    
    def is_full(self):
        """Check if slot is fully booked."""
        return self.booked_quantity >= self.capacity

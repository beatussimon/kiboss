"""
Asset Models for KIBOSS - Universal Asset System

This module implements the universal asset model that supports:
- Rooms (spaces, venues, offices)
- Tools (equipment, machinery)
- Vehicles (cars, bikes, boats)
- Seat services (ride-sharing)
- Time-based services (consultations, rentals by time)

Key features:
- Extensible asset types via JSONB properties
- Availability rules and pricing rules
- Unit capacity and time granularity
- Ownership and verification
- Jurisdiction metadata
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from kiboss.apps.common.validators import validate_file_size, validate_image_extension, validate_document_extension


class AssetType(models.TextChoices):
    """Enumeration of supported asset types."""
    ROOM = 'ROOM', 'Room/Space'
    TOOL = 'TOOL', 'Tool/Equipment'
    VEHICLE = 'VEHICLE', 'Vehicle'
    SEAT_SERVICE = 'SEAT_SERVICE', 'Seat Service (Ride-sharing)'
    TIME_SERVICE = 'TIME_SERVICE', 'Time-based Service'
    
    # Corporate Hospitality
    HOTEL = 'HOTEL', 'Hotel Property'
    RESTAURANT = 'RESTAURANT', 'Restaurant Property'
    HOTEL_ROOM = 'HOTEL_ROOM', 'Hotel Room'
    CONFERENCE_HALL = 'CONFERENCE_HALL', 'Conference Hall'
    DINING_TABLE = 'DINING_TABLE', 'Dining Table'


class VerificationStatus(models.TextChoices):
    """Asset verification status."""
    UNVERIFIED = 'UNVERIFIED', 'Unverified'
    PENDING = 'PENDING', 'Pending Review'
    VERIFIED = 'VERIFIED', 'Verified'
    REJECTED = 'REJECTED', 'Rejected'


class Asset(models.Model):
    """
    Universal Asset Model.
    
    This is the base model for all rental items in the system.
    Uses a flexible JSONB field for type-specific properties.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Hierarchy for Corporate Assets (Property -> Service)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_services',
        help_text="Parent property for services (e.g., Hotel for a Room)"
    )
    
    # Basic information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    asset_type = models.CharField(
        max_length=20,
        choices=AssetType.choices,
        default=AssetType.ROOM
    )
    
    # Ownership
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    
    # Corporate Flag
    is_corporate = models.BooleanField(default=False)
    
    # Location
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Tanzania', blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Jurisdiction (for legal compliance)
    jurisdiction = models.CharField(max_length=100, default='TZ')
    timezone = models.CharField(max_length=50, default='Africa/Dar_es_Salaam')
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED
    )
    verification_notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='verified_assets'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_listed = models.BooleanField(default=True)
    
    # Statistics
    total_bookings = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    total_reviews = models.IntegerField(default=0)
    
    # Flexible properties (JSONB in PostgreSQL, JSON in SQLite)
    properties = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'assets'
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
        indexes = [
            models.Index(fields=['asset_type']),
            models.Index(fields=['owner']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_listed']),
            models.Index(fields=['verification_status']),
            models.Index(fields=['average_rating']),
            models.Index(fields=['country', 'city']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_asset_type_display()})"
    
    def get_property(self, key, default=None):
        """Get a property value from the JSON field."""
        return self.properties.get(key, default)
        
    def set_property(self, key, value):
        """Set a property value in the JSON field."""
        self.properties[key] = value
        self.save(update_fields=['properties'])
    
    def clean(self):
        """
        Enforce business logic and hierarchy integrity.
        """
        from django.core.exceptions import ValidationError
        
        # 1. Circular Dependency Check
        if self.parent and self.parent == self:
            raise ValidationError({'parent': "An asset cannot be its own parent."})
            
        if self.parent and self.parent.parent:
             # Prevent deep nesting (>1 level) for now to keep architecture flat (Property -> Service)
             # If we need deeper nesting later (Resort -> Building -> Room), we can relax this.
             raise ValidationError({'parent': "Deep nesting is not allowed. Services must link directly to a root Property."})

        # 2. Hierarchy Type Integrity
        if self.parent:
            parent_type = self.parent.asset_type
            my_type = self.asset_type
            
            # Hotel Rules
            if my_type in [AssetType.HOTEL_ROOM, AssetType.CONFERENCE_HALL]:
                if parent_type != AssetType.HOTEL:
                    raise ValidationError({'parent': f"{self.get_asset_type_display()} must belong to a Hotel Property."})
            
            # Restaurant Rules
            if my_type == AssetType.DINING_TABLE:
                if parent_type != AssetType.RESTAURANT:
                    raise ValidationError({'parent': "Dining Tables must belong to a Restaurant Property."})
            
            # Standalone assets cannot have parents
            if my_type in [AssetType.VEHICLE, AssetType.TOOL, AssetType.HOTEL, AssetType.RESTAURANT]:
                raise ValidationError({'parent': f"{self.get_asset_type_display()} cannot be a child service."})

        # 10. LICENSE PLATE NORMALIZATION AND STRICT UNIQUENESS
        if self.asset_type == AssetType.VEHICLE and 'license_plate' in self.properties:
            plate = str(self.properties['license_plate']).replace(' ', '').upper()
            self.properties['license_plate'] = plate
            if Asset.objects.filter(properties__license_plate=plate).exclude(pk=self.pk).exists():
                raise ValidationError({'properties': "A vehicle with this strictly unique license plate already exists."})

        # 3. Vehicle Document Checks (Strict Reality)
        if self.asset_type == AssetType.VEHICLE and self.verification_status == VerificationStatus.VERIFIED:
            if self.pk:
                existing_docs = self.documents.values_list('document_type', flat=True)
                required_docs = ['REGISTRATION', 'INSURANCE', 'OWNERSHIP']
                missing = [doc for doc in required_docs if doc not in existing_docs]
                if missing:
                    raise ValidationError({'verification_status': f"Vehicle cannot be APPROVED without these documents: {', '.join(missing)}."})
            else:
                raise ValidationError({'verification_status': "Cannot verify a new vehicle before documents are uploaded."})

    def save(self, *args, **kwargs):
        """
        Enforce business rules and anti-fraud logic.
        """
        # Run standard validation
        self.clean()
        
        # Anti-Fraud: "Bait and Switch" Protection
        # If critical fields change on a VERIFIED asset, revoke status.
        if self.pk:
            try:
                original = Asset.objects.get(pk=self.pk)
                critical_fields = ['name', 'address', 'city', 'country', 'asset_type']
                is_changed = any(getattr(self, field) != getattr(original, field) for field in critical_fields)
                
                if is_changed and self.verification_status == VerificationStatus.VERIFIED:
                    self.verification_status = VerificationStatus.PENDING
                    self.verification_notes = f"System: Verification revoked due to changes in {', '.join(critical_fields)}."
                    self.is_listed = False # Delist immediately
            except Asset.DoesNotExist:
                # This should not happen if self.pk exists but just in case
                pass
        
        # Rule: Corporate assets cannot be listed until verified.
        if self.is_corporate and self.verification_status != VerificationStatus.VERIFIED:
            self.is_listed = False
            
        super().save(*args, **kwargs)


class AssetPhoto(models.Model):
    """Photos for assets."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    
    image = models.ImageField(upload_to='asset_photos/%Y/%m/', validators=[validate_file_size, validate_image_extension])
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'asset_photos'
        verbose_name = 'Asset Photo'
        verbose_name_plural = 'Asset Photos'
        ordering = ['order']
    
    def __str__(self):
        return f"Photo for {self.asset.name}"


class AssetDocument(models.Model):
    """Documents for asset verification (e.g., registration, insurance)."""
    
    DOCUMENT_TYPES = [
        ('REGISTRATION', 'Vehicle Registration'),
        ('INSURANCE', 'Insurance Policy'),
        ('INSPECTION', 'Safety Inspection'),
        ('OWNERSHIP', 'Proof of Ownership'),
        ('OTHER', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='asset_documents/%Y/%m/', validators=[validate_file_size, validate_document_extension])
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Expiry date for documents like insurance
    expiry_date = models.DateField(blank=True, null=True)
    
    # Verification status for this specific document
    is_verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_documents'
        verbose_name = 'Asset Document'
        verbose_name_plural = 'Asset Documents'
    
    def __str__(self):
        return f"{self.get_document_type_display()} for {self.asset.name}"


class AssetPricing(models.Model):
    """
    Pricing rules for assets.
    Supports multiple pricing tiers based on duration, quantity, etc.
    """
    
    UNIT_TYPES = [
        ('HOUR', 'Per Hour'),
        ('DAY', 'Per Day'),
        ('WEEK', 'Per Week'),
        ('MONTH', 'Per Month'),
        ('MILE', 'Per Mile'),
        ('KM', 'Per Kilometer'),
        ('SEAT', 'Per Seat'),
        ('FIXED', 'Fixed Price'),
        ('UNIT', 'Per Unit'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='pricing_rules'
    )
    
    name = models.CharField(max_length=100, help_text="e.g., 'Standard Hourly', 'Weekend Rate'")
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Quantity constraints
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(blank=True, null=True)
    
    # Duration constraints
    min_duration_minutes = models.PositiveIntegerField(default=0)
    max_duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    
    # Time-based availability
    available_from = models.TimeField(blank=True, null=True)
    available_to = models.TimeField(blank=True, null=True)
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text="List of days: [0,1,2,3,4,5,6] for Mon-Sun"
    )
    
    # Date-based availability
    valid_from = models.DateField(blank=True, null=True)
    valid_until = models.DateField(blank=True, null=True)
    
    # Pricing rules (JSON)
    quantity_discounts = models.JSONField(
        default=list,
        blank=True,
        help_text="Legacy quantity discount rules"
    )
    rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Discount rules, surge pricing, etc."
    )
    
    # Priority (higher priority rules apply first)
    priority = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_pricing'
        verbose_name = 'Asset Pricing'
        verbose_name_plural = 'Asset Pricing Rules'
        ordering = ['-priority']
    
    def __str__(self):
        return f"{self.asset.name} - {self.name} ({self.price}/{self.unit_type.lower()})"
    
    def calculate_price(self, quantity, duration_minutes=0, start_time=None, end_time=None):
        """
        Calculate price based on rules.
        
        Args:
            quantity: Number of units
            duration_minutes: Duration in minutes
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            Decimal: Calculated price
        """
        import math
        base_price = self.price
        
        time_multiplier = Decimal('1.0')
        if duration_minutes > 0:
            if self.unit_type == 'HOUR':
                time_multiplier = Decimal(str(max(1, math.ceil(duration_minutes / 60))))
            elif self.unit_type == 'DAY':
                time_multiplier = Decimal(str(max(1, math.ceil(duration_minutes / 1440))))
            elif self.unit_type == 'WEEK':
                time_multiplier = Decimal(str(max(1, math.ceil(duration_minutes / 10080))))
            elif self.unit_type == 'MONTH':
                time_multiplier = Decimal(str(max(1, math.ceil(duration_minutes / 43200))))
        
        base_price *= time_multiplier
        
        # Apply quantity discount if available
        discounts = self.quantity_discounts or self.rules.get('quantity_discounts', [])
        selected_multiplier = Decimal('1.0')
        for discount in discounts:
            if quantity >= discount.get('min_quantity', 0):
                selected_multiplier = Decimal(str(discount.get('multiplier', 1.0)))
        base_price *= selected_multiplier

        return base_price * quantity


class AssetAvailability(models.Model):
    """
    Availability rules for assets.
    Defines when an asset is available for booking.
    """
    
    AVAILABILITY_TYPES = [
        ('ALWAYS', 'Always Available'),
        ('SCHEDULED', 'Scheduled Availability'),
        ('CUSTOM', 'Custom Rules'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='availability_rules'
    )
    
    name = models.CharField(max_length=100)
    availability_type = models.CharField(max_length=20, choices=AVAILABILITY_TYPES)
    
    # Buffer time (minimum gap between bookings in minutes)
    buffer_minutes = models.PositiveIntegerField(default=0)
    
    # Advance booking limits
    min_advance_booking_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Minimum time before booking can be made"
    )
    max_advance_booking_days = models.PositiveIntegerField(
        default=90,
        help_text="Maximum days in advance a booking can be made"
    )
    
    # Custom schedule (JSON)
    schedule = models.JSONField(default=dict, blank=True)
    
    # Blocked dates (JSON array of date strings)
    blocked_dates = models.JSONField(default=list, blank=True)
    
    # Exception dates (JSON array of date strings with reason)
    exceptions = models.JSONField(default=list, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_availability'
        verbose_name = 'Asset Availability'
        verbose_name_plural = 'Asset Availability Rules'
    
    def __str__(self):
        return f"{self.asset.name} - {self.name}"
    
    def is_available(self, start_time, end_time):
        """
        Check if asset is available for given time slot.
        
        Args:
            start_time: datetime
            end_time: datetime
            
        Returns:
            tuple: (is_available, reason)
        """
        # Check buffer requirements
        # Check min/max advance booking
        # Check schedule
        # Check blocked dates
        # Check exceptions
        return True, None


class AssetCapacity(models.Model):
    """
    Capacity information for assets.
    Defines unit capacity, seating, etc.
    """
    
    CAPACITY_TYPES = [
        ('GUEST', 'Guest capacity'),
        ('SEAT', 'Seat capacity'),
        ('PARKING', 'Parking spots'),
        ('WORKSTATION', 'Workstations'),
        ('BED', 'Bed count'),
        ('UNIT', 'Unit count'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='capacities'
    )
    
    capacity_type = models.CharField(max_length=20, choices=CAPACITY_TYPES)
    quantity = models.PositiveIntegerField()
    description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'asset_capacity'
        verbose_name = 'Asset Capacity'
        verbose_name_plural = 'Asset Capacities'
    
    def __str__(self):
        return f"{self.asset.name} - {self.get_capacity_type_display()}: {self.quantity}"


class AssetTimeGranularity(models.Model):
    """
    Time granularity for asset bookings.
    Defines minimum and maximum booking durations.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='time_granularities'
    )
    
    # Minimum booking duration
    min_duration_minutes = models.PositiveIntegerField(default=60)
    
    # Maximum booking duration
    max_duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    
    # Booking increments (e.g., 15, 30, 60 minutes)
    increment_minutes = models.PositiveIntegerField(default=60)
    
    # Can bookings start at any time or only at specific intervals?
    any_start_time = models.BooleanField(default=True)
    allowed_start_times = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed start times in HH:MM format"
    )
    
    # Same-day booking allowed?
    same_day_booking = models.BooleanField(default=True)
    cutoff_hour = models.PositiveIntegerField(
        default=18,
        help_text="Hour of day after which same-day booking is not allowed"
    )
    
    class Meta:
        db_table = 'asset_time_granularity'
        verbose_name = 'Asset Time Granularity'
        verbose_name_plural = 'Asset Time Granularities'
    
    def __str__(self):
        return f"{self.asset.name} - Min: {self.min_duration_minutes}min, Increment: {self.increment_minutes}min"
    
    def validate_duration(self, duration_minutes):
        """Validate booking duration."""
        if duration_minutes < self.min_duration_minutes:
            return False, f"Duration must be at least {self.min_duration_minutes} minutes"
        if self.max_duration_minutes and duration_minutes > self.max_duration_minutes:
            return False, f"Duration cannot exceed {self.max_duration_minutes} minutes"
        if duration_minutes % self.increment_minutes != 0:
            return False, f"Duration must be in {self.increment_minutes} minute increments"
        return True, None
    
    def validate_start_time(self, start_time):
        """Validate booking start time."""
        if not self.any_start_time:
            if start_time.strftime('%H:%M') not in self.allowed_start_times:
                return False, "Start time not in allowed times"
        return True, None


class AssetJurisdiction(models.Model):
    """
    Jurisdiction-specific metadata for assets.
    Handles legal compliance across different regions.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.OneToOneField(
        Asset,
        on_delete=models.CASCADE,
        related_name='jurisdiction_info'
    )
    
    # Location details
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Legal requirements
    license_required = models.BooleanField(default=False)
    license_number = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(blank=True, null=True)
    
    insurance_required = models.BooleanField(default=False)
    insurance_details = models.TextField(blank=True)
    
    permits_required = models.JSONField(default=list, blank=True)
    
    # Tax information
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_category = models.CharField(max_length=50, blank=True)
    
    # Compliance notes
    compliance_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_jurisdiction'
        verbose_name = 'Asset Jurisdiction'
        verbose_name_plural = 'Asset Jurisdictions'
    
    def __str__(self):
        return f"{self.asset.name} - {self.country}/{self.state or ''}"


class AssetLike(models.Model):
    """Likes on assets (social feature)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_likes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'asset_likes'
        verbose_name = 'Asset Like'
        verbose_name_plural = 'Asset Likes'
        unique_together = ['asset', 'user']
    
    def __str__(self):
        return f"{self.user.email} likes {self.asset.name}"

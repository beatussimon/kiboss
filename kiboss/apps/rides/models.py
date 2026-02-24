"""
Ride Models for KIBOSS - Ride-Sharing Module

Treats rides as seat-based asset units with:
- Route definition
- Recurring schedules
- Seat capacity
- Pickup/dropoff points
- Seat-level booking
- Ride-specific contracts
- Passenger ↔ Driver ratings
- Impossible seat overbooking
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

from kiboss.apps.common.validators import validate_file_size, validate_image_extension


class RideStatus(models.TextChoices):
    """Ride status enumeration."""
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    OPEN = 'OPEN', 'Open for Booking'
    FULL = 'FULL', 'Full'
    DEPARTED = 'DEPARTED', 'Departed'
    IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class SeatBookingStatus(models.TextChoices):
    """Seat booking status."""
    RESERVED = 'RESERVED', 'Reserved (Pending Payment)'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    NO_SHOW = 'NO_SHOW', 'No Show'
    BOARDED = 'BOARDED', 'Boarded'
    COMPLETED = 'COMPLETED', 'Completed'


class CargoBookingStatus(models.TextChoices):
    """Cargo booking status."""
    RESERVED = 'RESERVED', 'Reserved (Pending Payment)'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    COMPLETED = 'COMPLETED', 'Completed'


class RideType(models.TextChoices):
    """Classification of the ride."""
    PERSONAL = 'PERSONAL', 'Personal Ride'
    BUSINESS = 'BUSINESS', 'Business Ride'


class Ride(models.Model):
    """
    Ride model for seat-based ride-sharing.
    
    A ride represents a single trip with defined route and schedule.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Owner/Driver
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='driven_rides'
    )
    
    # Vehicle reference (from assets) - optional, can specify vehicle details directly
    vehicle_asset = models.ForeignKey(
        'assets.Asset',
        on_delete=models.PROTECT,
        related_name='rides',
        null=True,
        blank=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=RideStatus.choices,
        default=RideStatus.SCHEDULED
    )
    
    # Ride classification
    ride_type = models.CharField(
        max_length=20,
        choices=RideType.choices,
        default=RideType.PERSONAL
    )
    
    # Route
    route_name = models.CharField(max_length=255)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    
    # Waypoints (JSON)
    waypoints = models.JSONField(default=list, blank=True)
    
    # Schedule
    departure_time = models.DateTimeField()
    estimated_arrival = models.DateTimeField(blank=True, null=True)
    actual_arrival = models.DateTimeField(blank=True, null=True)
    
    # Recurring schedule (if this is a template)
    is_recurring = models.BooleanField(default=False)
    recurring_pattern = models.JSONField(default=dict, blank=True)
    
    # Seat capacity
    total_seats = models.PositiveIntegerField(default=4)
    seat_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Cargo capacity
    cargo_enabled = models.BooleanField(default=False)
    total_cargo = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Total cargo capacity in kg or units")
    cargo_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Price per kg or unit")
    
    # Seat management
    reserved_seats = models.PositiveIntegerField(default=0)
    confirmed_seats = models.PositiveIntegerField(default=0)
    
    # Cargo management
    reserved_cargo = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    confirmed_cargo = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Vehicle details
    vehicle_description = models.CharField(max_length=255, blank=True)
    vehicle_color = models.CharField(max_length=50, blank=True)
    vehicle_license_plate = models.CharField(max_length=20, blank=True)
    
    # Driver notes
    driver_notes = models.TextField(blank=True)
    
    # Cancellation policy
    cancellation_cutoff_minutes = models.PositiveIntegerField(
        default=120,
        help_text="Minutes before departure after which cancellation is not allowed"
    )
    
    # No-show policy
    no_show_cutoff_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Minutes after departure to mark no-show"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'rides'
        verbose_name = 'Ride'
        verbose_name_plural = 'Rides'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['driver']),
            models.Index(fields=['departure_time']),
            models.Index(fields=['origin']),
            models.Index(fields=['destination']),
        ]
    
    def __str__(self):
        return f"Ride {self.id}: {self.origin} → {self.destination} ({self.departure_time})"

    def save(self, *args, **kwargs):
        # Update full status dynamically based on multiple capacity pools
        seats_full = (self.reserved_seats + self.confirmed_seats) >= self.total_seats
        cargo_full = not self.cargo_enabled or ((self.reserved_cargo + self.confirmed_cargo) >= self.total_cargo)
        
        status_changed = False
        if self.status in [RideStatus.OPEN, RideStatus.SCHEDULED]:
            if seats_full and cargo_full:
                self.status = RideStatus.FULL
                status_changed = True
        elif self.status == RideStatus.FULL:
            if not (seats_full and cargo_full):
                # Restore visibility if a cancellation happened
                if self.departure_time > timezone.now():
                    self.status = RideStatus.SCHEDULED
                    status_changed = True
        
        if status_changed and 'update_fields' in kwargs:
            update_fields = kwargs['update_fields']
            if update_fields is not None and 'status' not in update_fields:
                kwargs['update_fields'] = list(update_fields) + ['status']
                
        super().save(*args, **kwargs)
    
    def get_available_seats(self):
        """Get number of available seats (considering both reserved and confirmed)."""
        return max(0, self.total_seats - self.reserved_seats - self.confirmed_seats)
        
    def get_available_cargo(self):
        """Get available cargo capacity."""
        if not self.cargo_enabled:
            return Decimal('0.00')
        return max(Decimal('0.00'), self.total_cargo - self.reserved_cargo - self.confirmed_cargo)
    
    def is_full(self):
        """Check if ride is fully booked across all active capacity pools."""
        seats_full = (self.reserved_seats + self.confirmed_seats) >= self.total_seats
        cargo_full = not self.cargo_enabled or ((self.reserved_cargo + self.confirmed_cargo) >= self.total_cargo)
        return seats_full and cargo_full
    
    def can_book(self):
        """Check if ride accepts new bookings."""
        if self.status not in [RideStatus.OPEN, RideStatus.SCHEDULED]:
            return False, f"Ride is {self.status}"
        if self.is_full():
            return False, "Ride is full"
        if self.departure_time < timezone.now():
            return False, "Ride has already departed"
        return True, None


class RidePhoto(models.Model):
    """Photos for rides."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    
    image = models.ImageField(upload_to='ride_photos/%Y/%m/', validators=[validate_file_size, validate_image_extension])
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ride_photos'
        verbose_name = 'Ride Photo'
        verbose_name_plural = 'Ride Photos'
        ordering = ['order']
    
    def __str__(self):
        return f"Photo for Ride {self.ride.id}"


class RideStop(models.Model):
    """
    Pickup/dropoff points along the route.
    """
    
    STOP_TYPES = [
        ('PICKUP', 'Pickup Point'),
        ('DROPOFF', 'Drop-off Point'),
        ('BOTH', 'Both'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name='stops'
    )
    
    stop_type = models.CharField(max_length=20, choices=STOP_TYPES)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    
    # Location
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    
    # Scheduled times
    estimated_arrival = models.TimeField(blank=True, null=True)
    departure_time = models.TimeField(blank=True, null=True)
    
    # Order in route
    stop_order = models.PositiveIntegerField(default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ride_stops'
        verbose_name = 'Ride Stop'
        verbose_name_plural = 'Ride Stops'
        ordering = ['stop_order']
    
    def __str__(self):
        return f"Stop {self.stop_order}: {self.name} ({self.get_stop_type_display()})"


class SeatBooking(models.Model):
    """
    Individual seat booking on a ride.
    Each seat can be booked separately.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.PROTECT,
        related_name='seat_bookings'
    )
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ride_bookings'
    )
    
    # Seat assignment
    seat_number = models.PositiveIntegerField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=SeatBookingStatus.choices,
        default=SeatBookingStatus.RESERVED
    )
    
    # Pickup and dropoff stops
    pickup_stop = models.ForeignKey(
        RideStop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pickup_bookings'
    )
    dropoff_stop = models.ForeignKey(
        RideStop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='dropoff_bookings'
    )
    
    # Price
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Payment
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='seat_booking'
    )
    
    # Contract
    contract = models.OneToOneField(
        'contracts.Contract',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='seat_booking'
    )
    
    # Passenger details
    passenger_notes = models.TextField(blank=True)
    luggage_count = models.PositiveIntegerField(default=0)
    
    # Check-in
    checked_in_at = models.DateTimeField(blank=True, null=True)
    boarded_at = models.DateTimeField(blank=True, null=True)
    
    # No-show tracking
    marked_no_show_at = models.DateTimeField(blank=True, null=True)
    no_show_penalty_applied = models.BooleanField(default=False)
    
    # Cancellation
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seat_bookings'
        verbose_name = 'Seat Booking'
        verbose_name_plural = 'Seat Bookings'
        unique_together = ['ride', 'seat_number']
        indexes = [
            models.Index(fields=['ride']),
            models.Index(fields=['passenger']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Seat {self.seat_number} on {self.ride.id} - {self.passenger.email}"
    
    def assign_seat(self, seat_number):
        """Assign seat number (atomic operation)."""
        with transaction.atomic():
            # Lock the ride
            ride = Ride.objects.select_for_update().get(id=self.ride_id)
            
            # Check if seat is available
            if SeatBooking.objects.filter(
                ride=self.ride,
                seat_number=seat_number,
                status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
            ).exists():
                raise ValueError(f"Seat {seat_number} is not available")
            
            self.seat_number = seat_number
            self.save()
    
    def cancel(self, reason=''):
        """Cancel seat booking."""
        if self.status == SeatBookingStatus.CONFIRMED:
            self.status = SeatBookingStatus.CANCELLED
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.save()
            
            # Update ride seat counts
            self.ride.confirmed_seats = max(0, self.ride.confirmed_seats - 1)
            # We call save() to trigger the visibility logic update in Ride.save()
            self.ride.save()
    
    def mark_no_show(self):
        """Mark passenger as no-show."""
        self.status = SeatBookingStatus.NO_SHOW
        self.marked_no_show_at = timezone.now()
        self.no_show_penalty_applied = True
        self.save(update_fields=['status', 'marked_no_show_at', 'no_show_penalty_applied', 'updated_at'])


class RideSchedule(models.Model):
    """
    Recurring ride schedule template.
    Generates individual ride instances.
    """
    
    SCHEDULE_TYPES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('CUSTOM', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ride_schedules'
    )
    vehicle_asset = models.ForeignKey(
        'assets.Asset',
        on_delete=models.PROTECT,
        related_name='ride_schedules',
        blank=True,
        null=True
    )
    
    name = models.CharField(max_length=255)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES)
    ride_type = models.CharField(max_length=20, choices=RideType.choices, default=RideType.PERSONAL)
    
    # Route (copied to rides)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    waypoints = models.JSONField(default=list, blank=True)
    
    # Schedule details
    departure_time = models.TimeField()
    estimated_duration_minutes = models.PositiveIntegerField(default=60)
    
    # Recurrence pattern
    recurrence_days = models.JSONField(
        default=list,
        help_text="Days of week: [0,1,2,3,4,5,6] for Mon-Sun"
    )
    
    # Seat capacity and pricing
    total_seats = models.PositiveIntegerField(default=4)
    seat_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Cargo capacity and pricing
    cargo_enabled = models.BooleanField(default=False)
    total_cargo = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    cargo_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Validity period
    valid_from = models.DateField()
    valid_until = models.DateField(blank=True, null=True)
    
    # Active status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ride_schedules'
        verbose_name = 'Ride Schedule'
        verbose_name_plural = 'Ride Schedules'
    
    def __str__(self):
        return f"Schedule: {self.name} ({self.get_schedule_type_display()})"
    
    def generate_rides(self, days_ahead=30):
        """Generate ride instances for the schedule."""
        from datetime import datetime, timedelta
        
        rides_created = []
        current_date = max(timezone.now().date(), self.valid_from)
        end_date = current_date + timedelta(days=days_ahead)
        if self.valid_until:
            end_date = min(end_date, self.valid_until)

        vehicle_asset = self.vehicle_asset
        if vehicle_asset is None:
            vehicle_asset = self.driver.assets.filter(is_active=True).first()
        if vehicle_asset is None:
            return rides_created
        
        # Iterate through dates
        while current_date <= end_date:
            # Check if this day matches recurrence
            weekday = current_date.weekday()
            if weekday in self.recurrence_days:
                # Create departure datetime
                departure_datetime = datetime.combine(
                    current_date,
                    self.departure_time
                ).replace(tzinfo=timezone.get_current_timezone())
                
                # Create ride if not exists
                if not Ride.objects.filter(
                    driver=self.driver,
                    departure_time=departure_datetime,
                    origin=self.origin,
                    destination=self.destination
                ).exists():
                    ride = Ride.objects.create(
                        driver=self.driver,
                        vehicle_asset=vehicle_asset,
                        ride_type=self.ride_type,
                        route_name=self.name,
                        origin=self.origin,
                        destination=self.destination,
                        waypoints=self.waypoints,
                        departure_time=departure_datetime,
                        total_seats=self.total_seats,
                        seat_price=self.seat_price,
                        cargo_enabled=self.cargo_enabled,
                        total_cargo=self.total_cargo,
                        cargo_price=self.cargo_price,
                        currency=self.currency,
                        is_recurring=True,
                        recurring_pattern={
                            'schedule_id': str(self.id),
                            'pattern': self.recurrence_days
                        }
                    )
                    rides_created.append(ride)
            
            current_date += timedelta(days=1)
        
        return rides_created


# Import transaction for atomic operations
from django.db import transaction

class CargoBooking(models.Model):
    """
    Individual cargo booking on a ride.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.PROTECT,
        related_name='cargo_bookings'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cargo_shipments'
    )
    
    # Cargo details
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Weight or units booked")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=CargoBookingStatus.choices,
        default=CargoBookingStatus.RESERVED
    )
    
    # Stops
    pickup_stop = models.ForeignKey(
        RideStop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cargo_pickup_bookings'
    )
    dropoff_stop = models.ForeignKey(
        RideStop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cargo_dropoff_bookings'
    )
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cargo_booking'
    )
    
    # Cargo specific details
    cargo_description = models.TextField(blank=True, help_text="Description of items being shipped")
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # Cancellation tracking
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cargo_bookings'
        verbose_name = 'Cargo Booking'
        verbose_name_plural = 'Cargo Bookings'
        indexes = [
            models.Index(fields=['ride']),
            models.Index(fields=['sender']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Cargo {self.weight} on {self.ride.id} - {self.sender.email}"
        
    def cancel(self, reason=''):
        """Cancel cargo booking."""
        if self.status == CargoBookingStatus.CONFIRMED:
            self.status = CargoBookingStatus.CANCELLED
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.save()
            
            # Restore ride cargo capacity
            self.ride.confirmed_cargo = max(Decimal('0.00'), self.ride.confirmed_cargo - self.weight)
            # Save ride, which triggers the visibility capacity check automatically
            self.ride.save()

"""
Serializers for Rides API
"""
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from kiboss.apps.rides.models import Ride, RideStop, SeatBooking, RideSchedule, RidePhoto


class RidePhotoSerializer(serializers.ModelSerializer):
    """Serializer for ride photos."""
    
    url = serializers.ImageField(source='image', read_only=True)
    
    class Meta:
        model = RidePhoto
        fields = ['id', 'url', 'caption', 'order', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']
from kiboss.apps.users.serializers import UserSerializer
from kiboss.apps.assets.serializers import AssetSerializer


class RideStopSerializer(serializers.ModelSerializer):
    """Serializer for RideStop model."""
    
    class Meta:
        model = RideStop
        fields = [
            'id', 'stop_type', 'name', 'address',
            'latitude', 'longitude', 'estimated_arrival',
            'departure_time', 'stop_order', 'notes'
        ]
        read_only_fields = ['id']


class SeatBookingSerializer(serializers.ModelSerializer):
    """Serializer for SeatBooking model."""
    passenger = UserSerializer(read_only=True)
    pickup_stop_details = RideStopSerializer(source='pickup_stop', read_only=True)
    dropoff_stop_details = RideStopSerializer(source='dropoff_stop', read_only=True)
    booking_category = serializers.SerializerMethodField()
    ride_details = serializers.SerializerMethodField(source='ride')
    payment = serializers.SerializerMethodField()
    
    class Meta:
        model = SeatBooking
        fields = [
            'id', 'ride', 'ride_details', 'passenger', 'seat_number', 'status',
            'pickup_stop', 'pickup_stop_details',
            'dropoff_stop', 'dropoff_stop_details',
            'price', 'currency', 'payment',
            'passenger_notes', 'luggage_count',
            'checked_in_at', 'boarded_at',
            'marked_no_show_at', 'no_show_penalty_applied',
            'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at', 'booking_category'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_booking_category(self, obj):
        return 'ride'
        
    def get_ride_details(self, obj):
        from kiboss.apps.rides.serializers import RideListSerializer
        return RideListSerializer(obj.ride).data

    def get_payment(self, obj):
        if obj.payment:
            from kiboss.apps.payments.serializers import PaymentSerializer
            return PaymentSerializer(obj.payment).data
        return None


class RideMinimalSerializer(serializers.ModelSerializer):
    """Minimal ride serializer for booking list views.

    Only includes fields the frontend actually renders in booking cards.
    Avoids nesting full UserSerializer (driver) and AssetSerializer (vehicle).
    """
    photos = RidePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Ride
        fields = [
            'id', 'origin', 'destination', 'departure_time',
            'status', 'seat_price', 'currency', 'photos',
        ]
        read_only_fields = fields


class SeatBookingListSerializer(serializers.ModelSerializer):
    """Lightweight SeatBooking serializer for list views.

    Uses UserMinimalSerializer and RideMinimalSerializer to avoid
    the N+1 query explosion caused by the full nested serializers.
    """
    passenger = serializers.SerializerMethodField()
    ride_details = serializers.SerializerMethodField()
    booking_category = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = SeatBooking
        fields = [
            'id', 'ride', 'ride_details', 'passenger', 'seat_number', 'status',
            'price', 'currency', 'payment',
            'passenger_notes', 'luggage_count',
            'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at', 'booking_category',
        ]
        read_only_fields = fields

    def get_passenger(self, obj):
        from kiboss.apps.users.serializers import UserMinimalSerializer
        return UserMinimalSerializer(obj.passenger).data

    def get_ride_details(self, obj):
        return RideMinimalSerializer(obj.ride).data

    def get_booking_category(self, obj):
        return 'ride'

    def get_payment(self, obj):
        if obj.payment:
            from kiboss.apps.payments.serializers import PaymentSerializer
            return PaymentSerializer(obj.payment).data
        return None


class SeatBookingCreateSerializer(serializers.Serializer):
    """Serializer for creating seat bookings with validation."""
    ride_id = serializers.UUIDField()
    seat_number = serializers.IntegerField(min_value=0, default=0, required=False)
    pickup_stop_id = serializers.UUIDField(required=False, allow_null=True)
    dropoff_stop_id = serializers.UUIDField(required=False, allow_null=True)
    passenger_notes = serializers.CharField(required=False, allow_blank=True)
    luggage_count = serializers.IntegerField(min_value=0, default=0)
    cargo_weight_kg = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00, required=False)
    
    def validate(self, data):
        from kiboss.apps.rides.models import Ride, SeatBooking, RideStatus, SeatBookingStatus
        
        ride_id = data.get('ride_id')
        seat_number = data.get('seat_number')
        
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            raise serializers.ValidationError({'ride_id': 'Ride not found'})
        
        # Check ride status
        if ride.status not in [RideStatus.OPEN, RideStatus.SCHEDULED]:
            raise serializers.ValidationError({'ride_id': f'Ride is not available for booking (status: {ride.status})'})
        
        # Check if ride is full
        if ride.is_full():
            raise serializers.ValidationError({'ride_id': 'Ride is fully booked'})
        
        # Check if ride has departed
        if ride.departure_time < timezone.now():
            raise serializers.ValidationError({'ride_id': 'Ride has already departed'})
        
        from decimal import Decimal
        from django.db.models import Sum

        cargo_weight_kg = data.get('cargo_weight_kg', Decimal('0.00'))
        if cargo_weight_kg < 0:
            raise serializers.ValidationError({'cargo_weight_kg': 'Weight cannot be negative'})

        seat_number = data.get('seat_number', 0)
        if ride.is_cargo_only and seat_number > 0:
            raise serializers.ValidationError({'seat_number': 'Ride is cargo only; no passengers allowed'})
        elif not ride.is_cargo_only and seat_number <= 0 and cargo_weight_kg <= 0:
            raise serializers.ValidationError('Must provide either a valid seat number or cargo weight')

        # Check total vehicle capacity
        if ride.max_vehicle_weight_capacity_kg > 0 and cargo_weight_kg > 0:
            current_cargo = SeatBooking.objects.filter(
                ride=ride, status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
            ).aggregate(total=Sum('cargo_weight_kg'))['total'] or Decimal('0.00')
            if current_cargo + cargo_weight_kg > ride.max_vehicle_weight_capacity_kg:
                raise serializers.ValidationError({'cargo_weight_kg': f'Exceeds max vehicle capacity. Available: {max(Decimal("0.00"), ride.max_vehicle_weight_capacity_kg - current_cargo)} kg'})

        if ride.payment_required_before_approval:
            from kiboss.apps.payments.models import OfflinePaymentMethod
            has_methods = OfflinePaymentMethod.objects.filter(user=ride.driver, is_active=True).exists()
            if not has_methods:
                raise serializers.ValidationError({'ride_id': 'Driver requires payment before approval, but has no payment methods set up. Booking cannot proceed.'})

        # Calculate Extra Fees
        extra_fees = Decimal('0.00')
        if ride.is_cargo_only:
            extra_fees += ride.flat_cargo_fee
            if cargo_weight_kg > ride.allowable_free_weight_kg:
                extra_fees += (cargo_weight_kg - ride.allowable_free_weight_kg) * ride.price_per_excess_kg
        else:
            if cargo_weight_kg > ride.allowable_free_weight_kg:
                extra_fees += (cargo_weight_kg - ride.allowable_free_weight_kg) * ride.price_per_excess_kg
        
        data['extra_fees'] = extra_fees

        # Check if seat is already taken
        if seat_number > 0:
            existing = SeatBooking.objects.filter(
                ride=ride,
                seat_number=seat_number,
                status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
            ).exists()
            
            if existing:
                raise serializers.ValidationError({'seat_number': f'Seat {seat_number} is already taken'})
        
        # Validate stop IDs if provided
        pickup_stop_id = data.get('pickup_stop_id')
        if pickup_stop_id:
            if not ride.stops.filter(id=pickup_stop_id).exists():
                raise serializers.ValidationError({'pickup_stop_id': 'Invalid pickup stop'})
        
        dropoff_stop_id = data.get('dropoff_stop_id')
        if dropoff_stop_id:
            if not ride.stops.filter(id=dropoff_stop_id).exists():
                raise serializers.ValidationError({'dropoff_stop_id': 'Invalid dropoff stop'})
        
        # Store ride for later use
        data['ride'] = ride
        return data


class RideStopCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating RideStop with ride data."""
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, default=0)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, default=0)
    
    class Meta:
        model = RideStop
        fields = [
            'stop_type', 'name', 'address',
            'latitude', 'longitude', 'estimated_arrival',
            'departure_time', 'stop_order', 'notes'
        ]


class RideSerializer(serializers.ModelSerializer):
    """Serializer for Ride model."""
    driver = UserSerializer(read_only=True)
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    vehicle_asset = AssetSerializer(read_only=True)
    vehicle_asset_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    available_seats = serializers.SerializerMethodField()
    available_cargo = serializers.SerializerMethodField()
    stops = RideStopSerializer(many=True, read_only=True)
    stops_data = RideStopCreateSerializer(many=True, write_only=True, required=False)
    photos = RidePhotoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver', 'driver_email', 'vehicle_asset',
            'vehicle_asset_id', 'ride_type',
            'status', 'route_name', 'origin', 'destination',
            'waypoints', 'departure_time', 'estimated_arrival',
            'actual_arrival', 'is_recurring', 'recurring_pattern',
            'total_seats', 'seat_price', 'currency',
            'reserved_seats', 'confirmed_seats', 'available_seats',
            'cargo_enabled', 'total_cargo', 'cargo_price',
            'reserved_cargo', 'confirmed_cargo', 'available_cargo',
            'vehicle_description', 'vehicle_color', 'vehicle_license_plate',
            'driver_notes', 'cancellation_cutoff_minutes',
            'no_show_cutoff_minutes', 'stops', 'stops_data',
            'photos',
            'creation_location_lat', 'creation_location_lng',
            'start_location_lat', 'start_location_lng',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # 4. VEHICLE PHOTOS (NO DUPLICATION)
        if not ret.get('photos') and instance.vehicle_asset:
            request = self.context.get('request')
            ret['photos'] = [
                {
                    'id': str(photo.id),
                    'image': request.build_absolute_uri(photo.image.url) if (photo.image and request) else (photo.image.url if photo.image else None),
                    'caption': photo.caption,
                    'is_primary': photo.is_primary
                } 
                for photo in instance.vehicle_asset.photos.all()
            ]
        return ret
    
    def get_available_seats(self, obj):
        return obj.get_available_seats()
        
    def get_available_cargo(self, obj):
        return obj.get_available_cargo()

    def validate(self, attrs):
        vehicle_asset_id = attrs.pop('vehicle_asset_id', None)
        vehicle_asset = None
        
        if vehicle_asset_id:
            from kiboss.apps.assets.models import Asset
            try:
                vehicle_asset = Asset.objects.get(id=vehicle_asset_id)
                attrs['vehicle_asset'] = vehicle_asset
            except Asset.DoesNotExist as exc:
                raise serializers.ValidationError({'vehicle_asset_id': 'Vehicle asset not found'}) from exc
                
        # 3. VEHICLE STATE MACHINE (STRICT GATEKEEPING)
        if vehicle_asset:
            from kiboss.apps.assets.models import VerificationStatus
            if vehicle_asset.verification_status != VerificationStatus.VERIFIED:
                raise serializers.ValidationError({'vehicle_asset_id': 'Vehicle must be APPROVED to create a ride.'})
                
        # 1. VEHICLE SEATS (STRICT REALITY ENFORCEMENT)
        # Seats MUST be derived from vehicle: max_passenger_seats = vehicle.total_seats - 1 (driver)
        if vehicle_asset:
            seat_capacity = vehicle_asset.capacities.filter(capacity_type='SEAT').first()
            if seat_capacity and seat_capacity.quantity > 0:
                # Remove manual input and override with vehicle capacity
                attrs['total_seats'] = max(0, seat_capacity.quantity - 1)
            else:
                # Fallback if no specific capacity object exists, but reject if missing strict config
                raise serializers.ValidationError({'vehicle_asset_id': 'Vehicle must have a defined SEAT capacity.'})
                
        # 8 & 9. RIDE UNIQUENESS AND TIME CONFLICTS
        # Prevent overlaps and duplicates strictly at DB level before save
        driver = self.context['request'].user
        departure_time = attrs.get('departure_time')
        estimated_arrival = attrs.get('estimated_arrival')
        origin = attrs.get('origin')
        destination = attrs.get('destination')
        
        if departure_time and estimated_arrival:
            from kiboss.apps.rides.models import Ride, RideStatus
            from django.db.models import Q
            
            # Check Ride Uniqueness (Anti-duplication)
            duplicate_exists = Ride.objects.filter(
                driver=driver,
                vehicle_asset=vehicle_asset,
                departure_time=departure_time,
                origin=origin,
                destination=destination
            ).exclude(status__in=[RideStatus.CANCELLED, RideStatus.COMPLETED]).exists()
            
            if duplicate_exists:
                raise serializers.ValidationError("A duplicate ride with this exact route and time already exists.")
            
            # Check Time Conflicts (Cannot run multiple rides at the same time)
            time_conflict = Ride.objects.filter(
                driver=driver,
                status__in=[RideStatus.SCHEDULED, RideStatus.OPEN, RideStatus.FULL, RideStatus.IN_TRANSIT]
            ).filter(
                Q(departure_time__lt=estimated_arrival) & Q(estimated_arrival__gt=departure_time)
            )
            
            # If using specific vehicle, check vehicle conflicts too
            if vehicle_asset:
                time_conflict = time_conflict.filter(Q(driver=driver) | Q(vehicle_asset=vehicle_asset))
                
            if time_conflict.exists():
                raise serializers.ValidationError("Time conflict detected. You or this vehicle already have an active ride during this period.")
                
            # 15. VEHICLE RENTAL VS RIDE (LOCKING SYSTEM)
            if vehicle_asset:
                from kiboss.apps.bookings.models import Booking, BookingStatus
                rental_conflict = Booking.objects.filter(
                    asset=vehicle_asset,
                    status__in=[BookingStatus.CONFIRMED, BookingStatus.ACTIVE]
                ).filter(
                    Q(start_date__lt=estimated_arrival) & Q(end_date__gt=departure_time)
                ).exists()
                
                if rental_conflict:
                    raise serializers.ValidationError("Vehicle is currently rented out during this period and cannot be used for a ride.")
        
        return attrs
    
    def create(self, validated_data):
        """Create a ride with stops."""
        stops_data = validated_data.pop('stops_data', [])
        
        with transaction.atomic():
            ride = Ride.objects.create(**validated_data)
            
            # Create stops
            for stop_data in stops_data:
                RideStop.objects.create(ride=ride, **stop_data)
            
            return ride


class RideListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ride listings."""
    driver = UserSerializer(read_only=True)
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    available_seats = serializers.SerializerMethodField()
    available_cargo = serializers.SerializerMethodField()
    photos = RidePhotoSerializer(many=True, read_only=True)
    vehicle_asset = AssetSerializer(read_only=True)
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver', 'driver_email', 'status', 'ride_type',
            'origin', 'destination', 'route_name',
            'departure_time', 'total_seats', 'seat_price',
            'cargo_enabled', 'total_cargo', 'cargo_price',
            'currency', 'available_seats', 'confirmed_seats',
            'available_cargo', 'confirmed_cargo',
            'vehicle_description', 'photos', 'vehicle_asset'
        ]
        read_only_fields = fields
    
    def get_available_seats(self, obj):
        return obj.get_available_seats()
        
    def get_available_cargo(self, obj):
        return obj.get_available_cargo()


class RideScheduleSerializer(serializers.ModelSerializer):
    """Serializer for RideSchedule model."""
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    vehicle_asset_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = RideSchedule
        fields = [
            'id', 'driver', 'driver_email', 'name', 'schedule_type', 'ride_type',
            'vehicle_asset_id',
            'origin', 'destination', 'waypoints',
            'departure_time', 'estimated_duration_minutes',
            'recurrence_days', 'total_seats', 'seat_price',
            'cargo_enabled', 'total_cargo', 'cargo_price', 'currency',
            'valid_from', 'valid_until', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        vehicle_asset_id = attrs.pop('vehicle_asset_id', None)
        if vehicle_asset_id:
            from kiboss.apps.assets.models import Asset
            try:
                attrs['vehicle_asset'] = Asset.objects.get(id=vehicle_asset_id)
            except Asset.DoesNotExist as exc:
                raise serializers.ValidationError({'vehicle_asset_id': 'Vehicle asset not found'}) from exc
        return attrs

from kiboss.apps.rides.models import CargoBooking, CargoBookingStatus

class CargoBookingSerializer(serializers.ModelSerializer):
    """Serializer for CargoBooking model."""
    sender = UserSerializer(read_only=True)
    pickup_stop_details = RideStopSerializer(source='pickup_stop', read_only=True)
    dropoff_stop_details = RideStopSerializer(source='dropoff_stop', read_only=True)
    payment = serializers.SerializerMethodField()
    
    class Meta:
        model = CargoBooking
        fields = [
            'id', 'ride', 'sender', 'weight', 'status',
            'pickup_stop', 'pickup_stop_details',
            'dropoff_stop', 'dropoff_stop_details',
            'price', 'currency', 'payment',
            'cargo_description', 'recipient_name', 'recipient_phone',
            'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_payment(self, obj):
        if obj.payment:
            from kiboss.apps.payments.serializers import PaymentSerializer
            return PaymentSerializer(obj.payment).data
        return None

class CargoBookingCreateSerializer(serializers.Serializer):
    """Serializer for creating cargo bookings with validation."""
    ride_id = serializers.UUIDField()
    weight = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    pickup_stop_id = serializers.UUIDField(required=False, allow_null=True)
    dropoff_stop_id = serializers.UUIDField(required=False, allow_null=True)
    cargo_description = serializers.CharField(required=False, allow_blank=True)
    recipient_name = serializers.CharField(required=False, allow_blank=True)
    recipient_phone = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        from kiboss.apps.rides.models import Ride, RideStatus
        
        ride_id = data.get('ride_id')
        weight = data.get('weight')
        
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            raise serializers.ValidationError({'ride_id': 'Ride not found'})
            
        if not ride.cargo_enabled:
            raise serializers.ValidationError({'ride_id': 'Ride does not accept cargo'})
        
        # Check ride status
        if ride.status not in [RideStatus.OPEN, RideStatus.SCHEDULED]:
            raise serializers.ValidationError({'ride_id': f'Ride is not available for booking (status: {ride.status})'})
            
        # Check if cargo capacity is sufficient
        available_cargo = ride.get_available_cargo()
        if weight > available_cargo:
            raise serializers.ValidationError({
                'weight': f'Insufficient cargo capacity. Available: {available_cargo} kg/units.'
            })
        
        # Check if ride has departed
        if ride.departure_time < timezone.now():
            raise serializers.ValidationError({'ride_id': 'Ride has already departed'})
            
        # Validate stop IDs if provided
        pickup_stop_id = data.get('pickup_stop_id')
        if pickup_stop_id:
            if not ride.stops.filter(id=pickup_stop_id).exists():
                raise serializers.ValidationError({'pickup_stop_id': 'Invalid pickup stop'})
        
        dropoff_stop_id = data.get('dropoff_stop_id')
        if dropoff_stop_id:
            if not ride.stops.filter(id=dropoff_stop_id).exists():
                raise serializers.ValidationError({'dropoff_stop_id': 'Invalid dropoff stop'})
                
        data['ride'] = ride
        return data

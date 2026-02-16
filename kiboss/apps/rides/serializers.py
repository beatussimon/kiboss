"""
Serializers for Rides API
"""
from rest_framework import serializers
from django.utils import timezone
from kiboss.apps.rides.models import Ride, RideStop, SeatBooking, RideSchedule
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
    pickup_stop_details = RideStopSerializer(source='pickup_stop', read_only=True)
    dropoff_stop_details = RideStopSerializer(source='dropoff_stop', read_only=True)
    
    class Meta:
        model = SeatBooking
        fields = [
            'id', 'ride', 'passenger', 'seat_number', 'status',
            'pickup_stop', 'pickup_stop_details',
            'dropoff_stop', 'dropoff_stop_details',
            'price', 'currency', 'payment',
            'passenger_notes', 'luggage_count',
            'checked_in_at', 'boarded_at',
            'marked_no_show_at', 'no_show_penalty_applied',
            'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SeatBookingCreateSerializer(serializers.Serializer):
    """Serializer for creating seat bookings with validation."""
    ride_id = serializers.UUIDField()
    seat_number = serializers.IntegerField(min_value=1)
    pickup_stop_id = serializers.UUIDField(required=False, allow_null=True)
    dropoff_stop_id = serializers.UUIDField(required=False, allow_null=True)
    passenger_notes = serializers.CharField(required=False, allow_blank=True)
    luggage_count = serializers.IntegerField(min_value=0, default=0)
    
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
        
        # Check if seat is already taken
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


class RideSerializer(serializers.ModelSerializer):
    """Serializer for Ride model."""
    driver = UserSerializer(read_only=True)
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    vehicle_asset = AssetSerializer(read_only=True)
    available_seats = serializers.SerializerMethodField()
    stops = RideStopSerializer(many=True, read_only=True)
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver', 'driver_email', 'vehicle_asset',
            'status', 'route_name', 'origin', 'destination',
            'waypoints', 'departure_time', 'estimated_arrival',
            'actual_arrival', 'is_recurring', 'recurring_pattern',
            'total_seats', 'seat_price', 'currency',
            'reserved_seats', 'confirmed_seats', 'available_seats',
            'vehicle_description', 'vehicle_color', 'vehicle_license_plate',
            'driver_notes', 'cancellation_cutoff_minutes',
            'no_show_cutoff_minutes', 'stops',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_available_seats(self, obj):
        return obj.get_available_seats()


class RideListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ride listings."""
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    available_seats = serializers.SerializerMethodField()
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver_email', 'status',
            'origin', 'destination', 'route_name',
            'departure_time', 'total_seats',
            'seat_price', 'currency', 'available_seats',
            'vehicle_description'
        ]
        read_only_fields = fields
    
    def get_available_seats(self, obj):
        return obj.get_available_seats()


class RideScheduleSerializer(serializers.ModelSerializer):
    """Serializer for RideSchedule model."""
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    
    class Meta:
        model = RideSchedule
        fields = [
            'id', 'driver', 'driver_email', 'name', 'schedule_type',
            'origin', 'destination', 'waypoints',
            'departure_time', 'estimated_duration_minutes',
            'recurrence_days', 'total_seats', 'seat_price', 'currency',
            'valid_from', 'valid_until', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

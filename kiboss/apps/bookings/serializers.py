"""
Serializers for KIBOSS Booking API
"""

from rest_framework import serializers
from django.utils import timezone
from kiboss.apps.bookings.models import Booking, BookingStatus, BookingTimeline, BookingStatusTransition
from kiboss.apps.assets.serializers import AssetSummarySerializer
from kiboss.apps.users.serializers import UserSerializer


class BookingStatusTransitionSerializer(serializers.ModelSerializer):
    """Serializer for booking status transitions."""
    
    class Meta:
        model = BookingStatusTransition
        fields = [
            'id', 'from_status', 'to_status', 'actor_type',
            'actor_id', 'reason', 'justification', 'created_at'
        ]
        read_only_fields = fields


class BookingTimelineSerializer(serializers.ModelSerializer):
    """Serializer for booking timeline events."""
    
    class Meta:
        model = BookingTimeline
        fields = [
            'id', 'event_type', 'description', 'actor_type',
            'actor_id', 'data', 'created_at'
        ]
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating bookings."""
    
    asset_id = serializers.UUIDField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    renter_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate booking data."""
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError(
                "End time must be after start time"
            )
        
        if data['start_time'] < timezone.now():
            raise serializers.ValidationError(
                "Cannot book in the past"
            )

        # Backward compatibility for clients still sending renter_notes.
        if not data.get('notes') and data.get('renter_notes'):
            data['notes'] = data['renter_notes']

        return data


class BookingUpdateSerializer(serializers.Serializer):
    """Serializer for updating bookings."""
    
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BookingCancelSerializer(serializers.Serializer):
    """Serializer for cancelling bookings."""
    
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    justification = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BookingResponseSerializer(serializers.ModelSerializer):
    """Serializer for booking responses."""
    
    asset = AssetSummarySerializer(read_only=True)
    renter = UserSerializer(read_only=True)
    owner = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_hours = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'asset', 'renter', 'owner', 'status', 'status_display',
            'start_time', 'end_time', 'duration_hours', 'quantity',
            'unit_price', 'subtotal', 'service_fee', 'taxes',
            'total_price', 'currency', 'price_breakdown',
            'renter_notes', 'owner_notes',
            'is_late', 'late_minutes', 'late_fee_charged',
            'cancellation_fee', 'cancelled_at',
            'completed_at', 'created_at', 'updated_at',
            'can_cancel', 'can_start', 'can_complete'
        ]
        read_only_fields = fields
    
    def get_owner(self, obj):
        """Get the owner from the asset."""
        if hasattr(obj, 'asset') and obj.asset:
            return UserSerializer(obj.asset.owner).data
        return None
    
    def get_duration_hours(self, obj):
        return obj.get_duration_hours()
    
    def get_can_cancel(self, obj):
        can, _ = obj.is_cancellable()
        return can
    
    def get_can_start(self, obj):
        can, _ = obj.is_startable()
        return can
    
    def get_can_complete(self, obj):
        can, _ = obj.is_completable()
        return can


class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for listing bookings."""
    
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'asset_name', 'asset_id', 'status', 'status_display',
            'start_time', 'end_time', 'duration_hours', 'quantity',
            'total_price', 'currency', 'created_at'
        ]
        read_only_fields = fields
    
    def get_duration_hours(self, obj):
        return obj.get_duration_hours()


class BookingStartSerializer(serializers.Serializer):
    """Serializer for starting a booking."""
    
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BookingCompleteSerializer(serializers.Serializer):
    """Serializer for completing a booking."""
    
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    late_return = serializers.BooleanField(default=False)

"""
Serializers for KIBOSS Asset API
"""

from rest_framework import serializers
from kiboss.apps.assets.models import Asset, AssetPhoto, AssetPricing, AssetAvailability


class AssetPhotoSerializer(serializers.ModelSerializer):
    """Serializer for asset photos."""
    
    class Meta:
        model = AssetPhoto
        fields = ['id', 'image', 'caption', 'order', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetPricingSerializer(serializers.ModelSerializer):
    """Serializer for asset pricing rules."""
    
    class Meta:
        model = AssetPricing
        fields = [
            'id', 'name', 'unit_type', 'price',
            'min_quantity', 'max_quantity',
            'min_duration_minutes', 'max_duration_minutes',
            'available_from', 'available_to', 'days_of_week',
            'valid_from', 'valid_until', 'rules',
            'priority', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AssetAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for asset availability rules."""
    
    class Meta:
        model = AssetAvailability
        fields = [
            'id', 'name', 'availability_type',
            'buffer_minutes',
            'min_advance_booking_minutes', 'max_advance_booking_days',
            'schedule', 'blocked_dates', 'exceptions',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AssetSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for assets (used in bookings)."""
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_type', 'city', 'country',
            'average_rating', 'total_reviews'
        ]
        read_only_fields = fields


class AssetListSerializer(serializers.ModelSerializer):
    """Serializer for listing assets."""
    
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email',
            'city', 'state', 'country',
            'verification_status', 'verification_status_display',
            'is_active', 'is_listed',
            'average_rating', 'total_reviews',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class AssetDetailSerializer(serializers.ModelSerializer):
    """Serializer for asset details."""
    
    photos = AssetPhotoSerializer(many=True, read_only=True)
    pricing_rules = AssetPricingSerializer(many=True, read_only=True)
    availability_rules = AssetAvailabilitySerializer(many=True, read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'jurisdiction', 'timezone',
            'verification_status', 'verification_status_display',
            'verification_notes', 'verified_at',
            'is_active', 'is_listed',
            'average_rating', 'total_reviews',
            'properties',
            'photos', 'pricing_rules', 'availability_rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class AssetCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assets."""
    
    class Meta:
        model = Asset
        fields = [
            'name', 'description', 'asset_type',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'jurisdiction', 'timezone',
            'is_listed', 'properties'
        ]
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class AssetUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating assets."""
    
    class Meta:
        model = Asset
        fields = [
            'name', 'description',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'is_listed', 'properties'
        ]

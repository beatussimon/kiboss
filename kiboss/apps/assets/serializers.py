"""
Serializers for KIBOSS Asset API
"""

from rest_framework import serializers
from kiboss.apps.assets.models import Asset, AssetType, AssetPhoto, AssetPricing, AssetAvailability, AssetCapacity, AssetTimeGranularity


class AssetPhotoSerializer(serializers.ModelSerializer):
    """Serializer for asset photos."""
    
    url = serializers.ImageField(source='image', read_only=True)
    
    class Meta:
        model = AssetPhoto
        fields = ['id', 'url', 'caption', 'order', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetCapacitySerializer(serializers.ModelSerializer):
    """Serializer for asset capacity."""
    
    class Meta:
        model = AssetCapacity
        fields = ['capacity_type', 'quantity', 'description']


class AssetTimeGranularitySerializer(serializers.ModelSerializer):
    """Serializer for asset time granularity."""
    
    class Meta:
        model = AssetTimeGranularity
        fields = [
            'min_duration_minutes', 'max_duration_minutes',
            'increment_minutes', 'any_start_time', 'allowed_start_times',
            'same_day_booking', 'cutoff_hour'
        ]


class AssetPricingSerializer(serializers.ModelSerializer):
    """Serializer for asset pricing rules."""
    
    class Meta:
        model = AssetPricing
        fields = [
            'id', 'name', 'unit_type', 'price',
            'min_quantity', 'max_quantity',
            'min_duration_minutes', 'max_duration_minutes',
            'available_from', 'available_to', 'days_of_week',
            'valid_from', 'valid_until', 'quantity_discounts', 'rules',
            'priority', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AssetAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for asset availability rules."""
    
    available_from = serializers.TimeField(required=False, allow_null=True)
    available_to = serializers.TimeField(required=False, allow_null=True)
    
    class Meta:
        model = AssetAvailability
        fields = [
            'id', 'name', 'availability_type',
            'buffer_minutes',
            'min_advance_booking_minutes', 'max_advance_booking_days',
            'schedule', 'blocked_dates', 'exceptions',
            'available_from', 'available_to', 'days_of_week',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AssetSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for assets (used in bookings)."""
    
    is_verified = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_type', 'city', 'country',
            'average_rating', 'total_reviews', 'is_verified'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'


class AssetListSerializer(serializers.ModelSerializer):
    """Serializer for listing assets."""
    
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    is_verified = serializers.SerializerMethodField()
    photos = AssetPhotoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email',
            'city', 'state', 'country',
            'verification_status', 'verification_status_display', 'is_verified',
            'is_active', 'is_listed',
            'average_rating', 'total_reviews',
            'photos',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'
    
    def to_representation(self, instance):
        """Optimize photos query by using prefetched data."""
        self.fields['photos'] = AssetPhotoSerializer(many=True, read_only=True)
        return super().to_representation(instance)


class AssetDetailSerializer(serializers.ModelSerializer):
    """Serializer for asset details."""
    
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    photos = AssetPhotoSerializer(many=True, read_only=True)
    pricing_rules = AssetPricingSerializer(many=True, read_only=True)
    availability_rules = AssetAvailabilitySerializer(many=True, read_only=True)
    capacities = AssetCapacitySerializer(many=True, read_only=True)
    time_granularity = AssetTimeGranularitySerializer(read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    is_verified = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'jurisdiction', 'timezone',
            'verification_status', 'verification_status_display', 'is_verified',
            'verification_notes', 'verified_at',
            'is_active', 'is_listed',
            'average_rating', 'total_reviews',
            'properties',
            'photos', 'pricing_rules', 'availability_rules',
            'capacities', 'time_granularity',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'
    
    def to_representation(self, instance):
        """Prefetch related data for nested serializers."""
        # Try to get capacities and time_granularity from prefetched data
        try:
            capacities = getattr(instance, 'capacities', None)
            if capacities is not None:
                self.fields['capacities'] = AssetCapacitySerializer(capacities.all(), many=True)
        except AssetCapacity.DoesNotExist:
            pass
        
        try:
            time_granularity = getattr(instance, 'time_granularity', None)
            if time_granularity is not None:
                self.fields['time_granularity'] = AssetTimeGranularitySerializer(time_granularity)
        except AssetTimeGranularity.DoesNotExist:
            pass
        
        return super().to_representation(instance)


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


class AssetSerializer(serializers.ModelSerializer):
    """Full serializer for assets (for create/update)."""
    
    asset_type = serializers.ChoiceField(choices=AssetType.choices, required=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    is_verified = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'jurisdiction', 'timezone',
            'verification_status', 'verification_notes',
            'is_active', 'is_listed', 'is_verified',
            'average_rating', 'total_reviews',
            'properties',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'owner_email', 'average_rating', 'total_reviews', 'created_at', 'updated_at']
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'

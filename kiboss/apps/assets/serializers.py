"""
Serializers for KIBOSS Asset API
"""

from rest_framework import serializers
from kiboss.apps.assets.models import Asset, AssetType, AssetPhoto, AssetDocument, AssetPricing, AssetAvailability, AssetCapacity, AssetTimeGranularity, PromotedListing

class PromotedListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotedListing
        fields = ['id', 'asset', 'promotion_type', 'starts_at', 'ends_at', 'is_active', 'payment_reference', 'amount_paid', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetPhotoSerializer(serializers.ModelSerializer):
    """Serializer for asset photos."""
    
    url = serializers.ImageField(source='image', read_only=True)
    
    class Meta:
        model = AssetPhoto
        fields = ['id', 'url', 'caption', 'order', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetDocumentSerializer(serializers.ModelSerializer):
    """Serializer for asset documents."""
    
    class Meta:
        model = AssetDocument
        fields = [
            'id', 'document_type', 'file', 'name', 
            'description', 'expiry_date', 'is_verified',
            'verification_notes', 'created_at'
        ]
        read_only_fields = ['id', 'is_verified', 'verification_notes', 'created_at']


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
    photos = AssetPhotoSerializer(many=True, read_only=True)
    is_promoted = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_type', 'city', 'country',
            'average_rating', 'total_reviews', 'is_verified', 'photos', 'is_promoted'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'

    def get_is_promoted(self, obj):
        from django.utils import timezone
        from kiboss.apps.assets.models import PromotedListing
        now = timezone.now()
        return PromotedListing.objects.filter(
            asset=obj,
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now
        ).exists()


class AssetListSerializer(serializers.ModelSerializer):
    """Serializer for listing assets."""
    
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner = serializers.SerializerMethodField()
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    is_verified = serializers.SerializerMethodField()
    owner_verification_badge = serializers.SerializerMethodField()
    photos = AssetPhotoSerializer(many=True, read_only=True)
    pricing_rules = AssetPricingSerializer(many=True, read_only=True)
    is_promoted = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email', 'owner_verification_badge',
            'city', 'state', 'country',
            'verification_status', 'verification_status_display', 'is_verified',
            'is_active', 'is_listed', 'is_promoted',
            'average_rating', 'total_reviews',
            'properties', 'photos', 'pricing_rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'
        
    def get_is_promoted(self, obj):
        from django.utils import timezone
        from kiboss.apps.assets.models import PromotedListing
        now = timezone.now()
        return PromotedListing.objects.filter(
            asset=obj,
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now
        ).exists()
        
    def get_owner(self, obj):
        from kiboss.apps.users.serializers import PublicUserSerializer
        return PublicUserSerializer(obj.owner, context=self.context).data
    
    def get_owner_verification_badge(self, obj):
        """Return the asset owner's verification badge (tier + color)."""
        if obj.owner:
            return obj.owner.verification_badge
        return {'tier': 'none', 'color': None}
    
    def to_representation(self, instance):
        """Optimize photos query by using prefetched data."""
        self.fields['photos'] = AssetPhotoSerializer(many=True, read_only=True)
        return super().to_representation(instance)


class AssetDetailSerializer(serializers.ModelSerializer):
    """Serializer for asset details."""
    
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner = serializers.SerializerMethodField()
    photos = AssetPhotoSerializer(many=True, read_only=True)
    pricing_rules = AssetPricingSerializer(many=True, read_only=True)
    availability_rules = AssetAvailabilitySerializer(many=True, read_only=True)
    capacities = AssetCapacitySerializer(many=True, read_only=True)
    time_granularity = AssetTimeGranularitySerializer(read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    is_verified = serializers.SerializerMethodField()
    is_promoted = serializers.SerializerMethodField()
    
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
            'is_active', 'is_listed', 'is_promoted',
            'average_rating', 'total_reviews',
            'properties',
            'photos', 'pricing_rules', 'availability_rules',
            'capacities', 'time_granularity',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'
        
    def get_is_promoted(self, obj):
        from django.utils import timezone
        from kiboss.apps.assets.models import PromotedListing
        now = timezone.now()
        return PromotedListing.objects.filter(
            asset=obj,
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now
        ).exists()
        
    def get_owner(self, obj):
        from kiboss.apps.users.serializers import PublicUserSerializer
        return PublicUserSerializer(obj.owner, context=self.context).data
    
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
    pricing_rules = AssetPricingSerializer(many=True, required=False)
    is_promoted = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'description', 'asset_type',
            'owner', 'owner_email',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'jurisdiction', 'timezone',
            'verification_status', 'verification_notes',
            'is_active', 'is_listed', 'is_verified', 'is_promoted',
            'average_rating', 'total_reviews',
            'properties', 'pricing_rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'owner_email', 'average_rating', 'total_reviews', 'created_at', 'updated_at']
    
    def get_is_verified(self, obj):
        return obj.verification_status == 'VERIFIED'
    
    def get_is_promoted(self, obj):
        from django.utils import timezone
        from kiboss.apps.assets.models import PromotedListing
        now = timezone.now()
        return PromotedListing.objects.filter(
            asset=obj,
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now
        ).exists()

    def create(self, validated_data):
        pricing_rules_data = validated_data.pop('pricing_rules', [])
        asset = Asset.objects.create(**validated_data)
        for pricing_data in pricing_rules_data:
            AssetPricing.objects.create(asset=asset, **pricing_data)
        return asset

    def update(self, instance, validated_data):
        pricing_rules_data = validated_data.pop('pricing_rules', None)
        
        # Update asset fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update pricing rules if provided
        if pricing_rules_data is not None:
            # For simplicity, we'll replace all existing rules
            instance.pricing_rules.all().delete()
            for pricing_data in pricing_rules_data:
                AssetPricing.objects.create(asset=instance, **pricing_data)
                
        return instance

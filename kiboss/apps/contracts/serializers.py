"""
Serializers for Contracts API
"""
from rest_framework import serializers
from kiboss.apps.contracts.models import Contract, ContractVersion, ContractStatus


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'booking', 'version', 'status', 'status_display',
            'jurisdiction', 'governing_law', 'terms',
            'cancellation_policy', 'late_return_policy', 'damage_policy',
            'generated_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'generated_at', 'updated_at']


class ContractDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Contract model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    booking_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'booking', 'booking_details', 'version', 'status', 'status_display',
            'snapshot', 'jurisdiction', 'governing_law', 'terms',
            'cancellation_policy', 'late_return_policy', 'damage_policy',
            'owner_signature', 'renter_signature',
            'owner_accepted_at', 'renter_accepted_at',
            'admin_override', 'admin_override_reason',
            'generated_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'generated_at', 'updated_at']
    
    def get_booking_details(self, obj):
        if obj.booking:
            return {
                'id': str(obj.booking.id),
                'asset_name': obj.booking.asset.name if obj.booking.asset else None,
                'renter_email': obj.booking.renter.email if obj.booking.renter else None,
                'start_time': obj.booking.start_time.isoformat() if obj.booking.start_time else None,
                'end_time': obj.booking.end_time.isoformat() if obj.booking.end_time else None,
                'total_price': str(obj.booking.total_price) if obj.booking.total_price else None,
            }
        return None


class ContractCreateSerializer(serializers.Serializer):
    """Serializer for creating contracts."""
    booking_id = serializers.UUIDField()
    jurisdiction = serializers.CharField(max_length=100, default='US')
    governing_law = serializers.CharField(max_length=255, required=False, allow_blank=True)
    cancellation_policy = serializers.CharField(required=False, allow_blank=True)
    late_return_policy = serializers.CharField(required=False, allow_blank=True)
    damage_policy = serializers.CharField(required=False, allow_blank=True)


class ContractAcceptSerializer(serializers.Serializer):
    """Serializer for accepting contracts."""
    signature = serializers.JSONField(required=False, default=dict)


class ContractVersionSerializer(serializers.ModelSerializer):
    """Serializer for ContractVersion model."""
    
    class Meta:
        model = ContractVersion
        fields = [
            'id', 'contract', 'version', 'snapshot', 'changes',
            'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at']

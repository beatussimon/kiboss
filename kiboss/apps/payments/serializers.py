"""
Serializers for Payments API
"""
from rest_framework import serializers
from kiboss.apps.payments.models import (
    Payment, Dispute, PaymentStatus, PaymentMethod,
    OfflinePaymentMethod, SubscriptionPayment
)


class OfflinePaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for available offline payment methods."""
    class Meta:
        model = OfflinePaymentMethod
        fields = ['id', 'network_name', 'payment_number', 'account_name', 'instructions']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    offline_method_details = OfflinePaymentMethodSerializer(source='offline_method', read_only=True)
    manual_receipt_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'amount', 'currency',
            'payment_method', 'payment_method_display', 'status', 'status_display',
            'zenopay_transaction_id', 'zenopay_authorization_code',
            'card_last_four', 'card_brand',
            'escrow_amount', 'escrow_held_at', 'escrow_released_at',
            'refunded_amount', 'refunded_at', 'refund_reason',
            'penalty_amount', 'penalty_reason',
            'failure_code', 'failure_message',
            'manual_confirmation',
            'manual_receipt_url',
            'offline_method',
            'offline_method_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_manual_receipt_url(self, obj):
        if obj.manual_receipt:
            return obj.manual_receipt.url
        return None


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Payment model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    booking_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'booking_details', 'amount', 'currency',
            'payment_method', 'status', 'status_display',
            'zenopay_transaction_id', 'zenopay_authorization_code',
            'card_last_four', 'card_brand',
            'escrow_amount', 'escrow_held_at', 'escrow_released_at',
            'refunded_amount', 'refunded_at', 'refund_reason',
            'penalty_amount', 'penalty_reason',
            'failure_code', 'failure_message',
            'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
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


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating payments."""
    booking_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.CREDIT_CARD)
    card_number = serializers.CharField(max_length=16, required=False, allow_blank=True)
    card_expiry = serializers.CharField(max_length=5, required=False, allow_blank=True)
    card_cvv = serializers.CharField(max_length=4, required=False, allow_blank=True)


class PaymentActionSerializer(serializers.Serializer):
    """Serializer for payment actions."""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.CharField(required=False, allow_blank=True)


class DisputeSerializer(serializers.ModelSerializer):
    """Serializer for Dispute model."""
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'booking', 'payment', 'initiated_by',
            'reason', 'description', 'disputed_amount',
            'status', 'evidence',
            'resolution', 'resolution_notes', 'resolved_by',
            'created_at', 'updated_at', 'resolved_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DisputeCreateSerializer(serializers.Serializer):
    """Serializer for creating disputes."""
    booking_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=Dispute.DISPUTE_REASONS)
    description = serializers.CharField()
    disputed_amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    """Serializer for submitting subscription payment proofs."""
    payment_method_details = OfflinePaymentMethodSerializer(source='payment_method', read_only=True)
    
    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'user', 'plan_type', 'amount', 'currency', 'payment_method',
            'payment_method_details', 'confirmation_message', 'receipt_image',
            'status', 'admin_notes', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'status', 'admin_notes', 'created_at']

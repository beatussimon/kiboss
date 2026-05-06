"""
Serializers for Payments API
"""
from rest_framework import serializers
from kiboss.apps.payments.models import (
    Payment, Dispute, PaymentStatus, PaymentMethod,
    OfflinePaymentMethod, UserPaymentMethod, ManualPayment
)


class OfflinePaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for available offline payment methods."""
    # `name` alias — frontend uses method.name, network_name is the real field
    name = serializers.CharField(source='network_name', read_only=True)

    class Meta:
        model = OfflinePaymentMethod
        fields = [
            'id', 'name', 'network_name', 'payment_type', 'payment_number',
            'account_name', 'instructions', 'qr_code', 'qr_code_image',
            'qr_instructions', 'lipa_namba', 'display_order',
            'is_active', 'is_system_wide',
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    
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
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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





class UserPaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for user's own payment methods."""
    class Meta:
        model = UserPaymentMethod
        fields = [
            'id', 'payment_type', 'account_name', 'account_number', 
            'instructions', 'qr_code', 'is_active', 'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ManualPaymentSerializer(serializers.ModelSerializer):
    """Serializer for manual payment submissions for bookings."""
    payment_method_details = OfflinePaymentMethodSerializer(source='payment_method', read_only=True)
    user_payment_method_details = UserPaymentMethodSerializer(source='user_payment_method', read_only=True)
    booking_details = serializers.SerializerMethodField()
    
    class Meta:
        model = ManualPayment
        fields = [
            'id', 'booking_type', 'booking_id', 'booking_details',
            'amount', 'currency', 'payment_method', 'payment_method_details',
            'user_payment_method', 'user_payment_method_details',
            'transaction_id', 'confirmation_message', 'receipt_image',
            'status', 'admin_notes', 'reviewed_at', 'reviewed_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'admin_notes', 'reviewed_at', 'reviewed_by', 'created_at', 'updated_at']
    
    def get_booking_details(self, obj):
        booking = obj.booking
        if booking:
            if obj.booking_type == 'ASSET':
                return {
                    'type': 'ASSET',
                    'id': str(booking.id),
                    'asset_name': booking.asset.name if booking.asset else None,
                    'renter_email': booking.renter.email if booking.renter else None,
                    'start_time': booking.start_time.isoformat() if booking.start_time else None,
                    'end_time': booking.end_time.isoformat() if booking.end_time else None,
                    'total_price': str(booking.total_price) if booking.total_price else None,
                }
            elif obj.booking_type == 'RIDE':
                return {
                    'type': 'RIDE',
                    'id': str(booking.id),
                    'ride_route': f"{booking.ride.origin} → {booking.ride.destination}" if booking.ride else None,
                    'passenger_email': booking.passenger.email if booking.passenger else None,
                    'seat_number': booking.seat_number,
                    'price': str(booking.price) if booking.price else None,
                }
            elif obj.booking_type == 'SUBSCRIPTION':
                return {
                    'type': 'SUBSCRIPTION',
                    'id': str(booking.id),
                    'plan_type': getattr(booking, 'plan_type', None),
                    'user_email': booking.user.email if hasattr(booking, 'user') else (booking.profile.user.email if hasattr(booking, 'profile') else None),
                }
        return None

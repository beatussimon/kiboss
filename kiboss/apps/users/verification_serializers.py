"""
Verification Serializers for KIBOSS
"""

from rest_framework import serializers
from .verification_models import (
    VerificationRequest, VerificationDocument,
    VerificationType, VerificationStatus
)


class VerificationRequestSerializer(serializers.ModelSerializer):
    """Serializer for verification requests."""
    
    verification_type_display = serializers.CharField(
        source='get_verification_type_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = VerificationRequest
        fields = [
            'id', 'verification_type', 'verification_type_display',
            'status', 'status_display',
            'email', 'phone',
            'document_type', 'document_number', 'document_country',
            'document_front', 'document_back', 'selfie',
            'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country',
            'rejection_reason', 'review_notes',
            'submitted_at', 'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'status', 'rejection_reason', 'review_notes',
            'reviewed_at', 'submitted_at'
        ]


class VerificationRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating verification requests."""
    
    class Meta:
        model = VerificationRequest
        fields = [
            'verification_type',
            'email', 'phone',
            'document_type', 'document_number', 'document_country',
            'document_front', 'document_back', 'selfie',
            'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country', 'proof_of_address'
        ]
    
    def validate(self, data):
        """Validate verification request data."""
        verification_type = data.get('verification_type')
        
        if verification_type == VerificationType.EMAIL:
            if not data.get('email'):
                raise serializers.ValidationError({
                    'email': 'Email is required for email verification'
                })
        
        elif verification_type == VerificationType.PHONE:
            if not data.get('phone'):
                raise serializers.ValidationError({
                    'phone': 'Phone is required for phone verification'
                })
        
        elif verification_type == VerificationType.IDENTITY:
            if not data.get('document_type'):
                raise serializers.ValidationError({
                    'document_type': 'Document type is required for identity verification'
                })
            if not data.get('document_front'):
                raise serializers.ValidationError({
                    'document_front': 'Front of ID document is required'
                })
            if not data.get('selfie'):
                raise serializers.ValidationError({
                    'selfie': 'Selfie with ID document is required'
                })
        
        elif verification_type == VerificationType.ADDRESS:
            if not data.get('address_line1'):
                raise serializers.ValidationError({
                    'address_line1': 'Address is required for address verification'
                })
            if not data.get('city'):
                raise serializers.ValidationError({
                    'city': 'City is required for address verification'
                })
            if not data.get('country'):
                raise serializers.ValidationError({
                    'country': 'Country is required for address verification'
                })
        
        return data


class VerificationRequestReviewSerializer(serializers.Serializer):
    """Serializer for reviewing verification requests."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data.get('action') == 'reject' and not data.get('reason'):
            raise serializers.ValidationError({
                'reason': 'Rejection reason is required when rejecting'
            })
        return data


class VerificationCodeSerializer(serializers.Serializer):
    """Serializer for verification code submission."""
    
    code = serializers.CharField(max_length=10, min_length=4)


class VerificationDocumentSerializer(serializers.ModelSerializer):
    """Serializer for verification documents."""
    
    class Meta:
        model = VerificationDocument
        fields = [
            'id', 'verification_request', 'document_type',
            'document', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VerificationStatusSerializer(serializers.Serializer):
    """Serializer for overall verification status."""
    
    email_verified = serializers.BooleanField()
    phone_verified = serializers.BooleanField()
    identity_verified = serializers.BooleanField()
    verification_tier = serializers.CharField()
    pending_requests = serializers.IntegerField()

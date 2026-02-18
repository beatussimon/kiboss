"""
Verification Views for KIBOSS

API endpoints for user verification workflow.
"""

import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .verification_models import (
    VerificationRequest, VerificationDocument,
    VerificationType, VerificationStatus
)
from .verification_serializers import (
    VerificationRequestSerializer, VerificationRequestCreateSerializer,
    VerificationRequestReviewSerializer, VerificationDocumentSerializer,
    VerificationCodeSerializer
)

logger = logging.getLogger(__name__)


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission check for owner or admin."""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


class VerificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing verification requests.
    
    Endpoints:
    - GET /verification/ - List user's verification requests
    - POST /verification/ - Create new verification request
    - GET /verification/{id}/ - Get verification details
    - POST /verification/{id}/submit/ - Submit for review
    - POST /verification/{id}/verify_code/ - Verify email/phone code
    - POST /verification/{id}/resend_code/ - Resend verification code
    - POST /verification/{id}/review/ - Admin review (approve/reject)
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VerificationRequestCreateSerializer
        if self.action == 'review':
            return VerificationRequestReviewSerializer
        if self.action == 'verify_code':
            return VerificationCodeSerializer
        return VerificationRequestSerializer
    
    def get_queryset(self):
        """Filter verification requests to user's own or all for admin."""
        queryset = VerificationRequest.objects.select_related('user').prefetch_related('additional_documents')
        
        if self.request.user.is_staff:
            # Admin can see all requests
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            type_filter = self.request.query_params.get('type')
            if type_filter:
                queryset = queryset.filter(verification_type=type_filter)
        else:
            # Regular users only see their own
            queryset = queryset.filter(user=self.request.user)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create verification request for current user."""
        # Check for existing pending request of same type
        existing = VerificationRequest.objects.filter(
            user=self.request.user,
            verification_type=serializer.validated_data['verification_type'],
            status__in=[VerificationStatus.PENDING, VerificationStatus.SUBMITTED, VerificationStatus.UNDER_REVIEW]
        ).first()
        
        if existing:
            raise ValueError(f"You already have a pending {existing.get_verification_type_display()} verification")
        
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create verification request."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_create(serializer)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # For email/phone verification, generate and send code
        instance = serializer.instance
        if instance.verification_type in [VerificationType.EMAIL, VerificationType.PHONE]:
            code = instance.generate_code()
            # TODO: Send code via email/SMS
            logger.info(f"Verification code for {instance.user.email}: {code}")
        
        return Response(
            VerificationRequestSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit verification request for review."""
        verification = self.get_object()
        
        if verification.status not in [VerificationStatus.PENDING]:
            return Response(
                {'error': 'Can only submit pending verification requests'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check required documents for identity verification
        if verification.verification_type == VerificationType.IDENTITY:
            if not verification.document_front or not verification.selfie:
                return Response(
                    {'error': 'Identity verification requires ID document and selfie'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        verification.submit()
        
        return Response(VerificationRequestSerializer(verification).data)
    
    @action(detail=True, methods=['post'])
    def verify_code(self, request, pk=None):
        """Verify email/phone verification code."""
        verification = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if verification.verification_type not in [VerificationType.EMAIL, VerificationType.PHONE]:
            return Response(
                {'error': 'Code verification only for email/phone'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        code = serializer.validated_data['code']
        success, message = verification.verify_code(code)
        
        if success:
            # Trigger notification
            from kiboss.apps.notifications.services import NotificationService
            NotificationService.notify_verification_approved(verification.user)
            
            return Response({
                'status': 'verified',
                'message': message
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resend_code(self, request, pk=None):
        """Resend verification code."""
        verification = self.get_object()
        
        if verification.verification_type not in [VerificationType.EMAIL, VerificationType.PHONE]:
            return Response(
                {'error': 'Code resend only for email/phone verification'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if verification.status == VerificationStatus.APPROVED:
            return Response(
                {'error': 'Already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check rate limit (max 3 resends per hour)
        if verification.code_attempts >= 3:
            return Response(
                {'error': 'Too many attempts. Please wait before requesting another code.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        code = verification.generate_code()
        # TODO: Send code via email/SMS
        logger.info(f"New verification code for {verification.user.email}: {code}")
        
        return Response({'message': 'Verification code sent'})
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def review(self, request, pk=None):
        """Review verification request (admin only)."""
        verification = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if verification.status not in [VerificationStatus.SUBMITTED, VerificationStatus.UNDER_REVIEW]:
            return Response(
                {'error': 'Can only review submitted verification requests'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action_type = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')
        reason = serializer.validated_data.get('reason', '')
        
        if action_type == 'approve':
            verification.approve(reviewer=request.user, notes=notes)
            
            # Send notification
            from kiboss.apps.notifications.services import NotificationService
            NotificationService.notify_verification_approved(verification.user)
            
            logger.info(f"Verification {verification.id} approved by {request.user.email}")
            
        elif action_type == 'reject':
            if not reason:
                return Response(
                    {'error': 'Rejection reason is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            verification.reject(reviewer=request.user, reason=reason, notes=notes)
            
            # Send notification
            from kiboss.apps.notifications.services import NotificationService
            NotificationService.notify_verification_rejected(verification.user, reason)
            
            logger.info(f"Verification {verification.id} rejected by {request.user.email}: {reason}")
        
        return Response(VerificationRequestSerializer(verification).data)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get overall verification status for current user."""
        user = request.user
        
        verifications = VerificationRequest.objects.filter(user=user)
        
        return Response({
            'email_verified': user.is_email_verified,
            'phone_verified': user.is_phone_verified,
            'identity_verified': user.is_identity_verified,
            'verification_tier': user.verification_tier,
            'pending_requests': verifications.filter(
                status__in=[VerificationStatus.PENDING, VerificationStatus.SUBMITTED, VerificationStatus.UNDER_REVIEW]
            ).count(),
            'latest_requests': {
                v_type: VerificationRequestSerializer(
                    verifications.filter(verification_type=v_type).first()
                ).data if verifications.filter(verification_type=v_type).exists() else None
                for v_type in [VerificationType.EMAIL, VerificationType.PHONE, VerificationType.IDENTITY]
            }
        })


class VerificationDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing verification documents.
    """
    
    serializer_class = VerificationDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return VerificationDocument.objects.filter(
            verification_request__user=self.request.user
        )
    
    def perform_create(self, serializer):
        verification_id = self.request.data.get('verification_request')
        verification = get_object_or_404(
            VerificationRequest,
            id=verification_id,
            user=self.request.user
        )
        serializer.save(verification_request=verification)

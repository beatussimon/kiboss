"""
Views for Payments API
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from kiboss.apps.payments.models import (
    Payment, Dispute, PaymentStatus, 
    OfflinePaymentMethod, SubscriptionPayment
)
from kiboss.apps.payments.serializers import (
    PaymentSerializer, PaymentDetailSerializer,
    PaymentCreateSerializer, PaymentActionSerializer,
    DisputeSerializer, DisputeCreateSerializer,
    OfflinePaymentMethodSerializer, SubscriptionPaymentSerializer
)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
    """
    queryset = Payment.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get payment summary for the current user."""
        user = request.user
        
        # Total paid (as renter)
        total_paid = Payment.objects.filter(
            booking__renter=user,
            status__in=[PaymentStatus.ESCROW, PaymentStatus.RELEASED]
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Total received (as owner)
        total_received = Payment.objects.filter(
            booking__asset__owner=user,
            status=PaymentStatus.RELEASED
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # In Escrow (as owner or renter)
        in_escrow = Payment.objects.filter(
            booking__asset__owner=user,
            status=PaymentStatus.ESCROW
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'total_paid': total_paid,
            'total_received': total_received,
            'in_escrow': in_escrow
        })
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentSerializer
        elif self.action == 'retrieve':
            return PaymentDetailSerializer
        elif self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'booking', 'booking__asset', 'booking__renter'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by booking
        booking_id = self.request.query_params.get('booking_id')
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        # Filter by user (renter or owner)
        user = self.request.user
        queryset = queryset.filter(
            booking__renter=user
        ) | queryset.filter(booking__asset__owner=user)
        
        return queryset.distinct()
    
    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        """Authorize payment (simulate)."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.PENDING:
            return Response(
                {'error': 'Payment is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Simulate authorization
        card_details = {
            'last_four': request.data.get('card_last_four', '4242'),
            'brand': request.data.get('card_brand', 'VISA')
        }
        payment.authorize(payment.amount, card_details)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def hold_escrow(self, request, pk=None):
        """Move funds to escrow."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.AUTHORIZED:
            return Response(
                {'error': 'Payment must be authorized first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = request.data.get('amount')
        payment.hold_in_escrow(amount)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def release_escrow(self, request, pk=None):
        """Release escrow funds."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.ESCROW:
            return Response(
                {'error': 'Payment is not in escrow'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        release_amount = request.data.get('amount')
        deduct_fees = request.data.get('fees')
        payment.release_from_escrow(release_amount, deduct_fees)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Process refund."""
        payment = self.get_object()
        
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        payment.refund(amount, reason)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)


class DisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing disputes.
    """
    queryset = Dispute.objects.all().order_by('-created_at')
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Dispute.objects.select_related(
            'booking', 'payment', 'initiated_by'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user
        user = self.request.user
        queryset = queryset.filter(
            initiated_by=user
        ) | queryset.filter(
            booking__renter=user
        ) | queryset.filter(
            booking__asset__owner=user
        )
        
        return queryset.distinct()
    
    def create(self, request, *args, **kwargs):
        """Create a new dispute."""
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from kiboss.apps.bookings.models import Booking
        
        booking_id = serializer.validated_data['booking_id']
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is party to the booking
        if request.user != booking.renter and request.user != booking.asset.owner:
            return Response(
                {'error': 'You are not a party to this booking'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if payment exists
        try:
            payment = booking.payment_info
        except Payment.DoesNotExist:
            return Response(
                {'error': 'No payment found for this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            dispute = Dispute.objects.create(
                booking=booking,
                payment=payment,
                initiated_by=request.user,
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data['description'],
                disputed_amount=serializer.validated_data['disputed_amount']
            )
            
            # Freeze payment
            payment.freeze_for_dispute()
        
        response_serializer = DisputeSerializer(dispute)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a dispute (admin only).."""
        dispute = self.get_object()
        
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can resolve disputes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        resolution = request.data.get('resolution')
        notes = request.data.get('notes', '')
        
        dispute.resolve(resolution, notes, request.user)
        
        serializer = DisputeSerializer(dispute)
        return Response(serializer.data)


class OfflinePaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset to list active offline payment methods."""
    queryset = OfflinePaymentMethod.objects.filter(is_active=True)
    serializer_class = OfflinePaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]


class SubscriptionPaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for users to submit manual payment proofs for subscriptions."""
    queryset = SubscriptionPayment.objects.all().order_by('-created_at')
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
        
    def perform_create(self, serializer):
        from kiboss.apps.payments.models import SubscriptionPayment
        serializer.save(user=self.request.user, status=SubscriptionPayment.Status.PENDING)

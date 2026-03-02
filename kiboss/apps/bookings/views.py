"""
Views for KIBOSS Booking API
"""

import logging
import re
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from kiboss.apps.bookings.models import Booking
from kiboss.apps.bookings.serializers import (
    BookingCreateSerializer, BookingResponseSerializer,
    BookingUpdateSerializer,
    BookingCancelSerializer, BookingCompleteSerializer, BookingTimelineSerializer
)
from kiboss.apps.bookings.services import BookingService, BookingError

logger = logging.getLogger(__name__)

# UUID pattern for validation
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class BookingViewSet(viewsets.ViewSet):
    """
    ViewSet for managing bookings.
    
    Endpoints:
    - POST /bookings/ - Create a new booking
    - GET /bookings/ - List user's bookings
    - GET /bookings/{id}/ - Get booking details
    - POST /bookings/{id}/cancel/ - Cancel a booking
    - POST /bookings/{id}/start/ - Start a booking
    - POST /bookings/{id}/complete/ - Complete a booking
    - GET /bookings/{id}/timeline/ - Get booking timeline
    """
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def new(self, request):
        """
        Return an empty booking form template for creating a new booking.
        This endpoint is used by the frontend to initialize a new booking.
        """
        return Response({
            'message': 'Use POST /api/v1/bookings/ to create a new booking',
            'allowed_params': [
                'asset_id', 'start_time', 'end_time', 'quantity', 'notes'
            ]
        })
    
    def list(self, request):
        """List user's bookings with optional filtering."""
        role = request.query_params.get('role')
        
        if role == 'RENTER':
            queryset = Booking.objects.filter(renter=request.user)
        elif role == 'OWNER':
            queryset = Booking.objects.filter(asset__owner=request.user)
        else:
            # Get bookings where user is renter or asset owner
            as_renter = Booking.objects.filter(renter=request.user)
            as_owner = Booking.objects.filter(asset__owner=request.user)
            queryset = (as_renter | as_owner).distinct()
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by asset
        asset_id = request.query_params.get('asset_id')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        queryset = queryset.order_by('-created_at')
        serializer = BookingResponseSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get booking details."""
        # Handle non-UUID pk values (like 'new') - return 404 instead of 500
        if pk and not UUID_PATTERN.match(str(pk)):
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            booking = Booking.objects.select_related('asset', 'asset__owner').get(pk=pk)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BookingResponseSerializer(booking)
        return Response(serializer.data)
    
    def create(self, request):
        """Create a new booking."""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            booking = BookingService.create_booking(
                renter=request.user,
                asset_id=serializer.validated_data['asset_id'],
                start_time=serializer.validated_data['start_time'],
                end_time=serializer.validated_data['end_time'],
                quantity=serializer.validated_data.get('quantity', 1),
                notes=serializer.validated_data.get('notes', ''),
                driver_license_number=serializer.validated_data.get('driver_license_number'),
                driving_experience_years=serializer.validated_data.get('driving_experience_years')
            )
            
            # Return full booking details
            response_serializer = BookingResponseSerializer(booking)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except BookingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error creating booking")
            return Response(
                {'error': 'An error occurred while creating booking'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, pk=None):
        """Update booking (only notes and non-critical fields)."""
        try:
            booking = Booking.objects.get(pk=pk, renter=request.user)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BookingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            if serializer.validated_data.get('notes'):
                booking.renter_notes = serializer.validated_data['notes']
                booking.save()
        
        response_serializer = BookingResponseSerializer(booking)
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a booking (legacy compatibility endpoint)."""
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            booking = BookingService.confirm_booking(booking_id=pk, actor=request.user)
            return Response(BookingResponseSerializer(booking).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking."""
        serializer = BookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            booking = BookingService.cancel_booking(
                booking_id=pk,
                actor=request.user,
                reason=serializer.validated_data.get('reason', ''),
                justification=serializer.validated_data.get('justification', '')
            )
            
            response_serializer = BookingResponseSerializer(booking)
            return Response(response_serializer.data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a booking (transition to ACTIVE)."""
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only renter can start
        if booking.renter != request.user:
            return Response(
                {'error': 'Only the renter can start the booking'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            booking = BookingService.start_booking(
                booking_id=pk,
                actor=request.user
            )
            
            response_serializer = BookingResponseSerializer(booking)
            return Response(response_serializer.data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete a booking (transition to COMPLETED)."""
        serializer = BookingCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only renter can complete
        if booking.renter != request.user:
            return Response(
                {'error': 'Only the renter can complete the booking'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            booking = BookingService.complete_booking(
                booking_id=pk,
                actor=request.user,
                notes=serializer.validated_data.get('notes', ''),
                late_return=serializer.validated_data.get('late_return', False)
            )
            
            response_serializer = BookingResponseSerializer(booking)
            return Response(response_serializer.data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """Authorize payment and move booking into confirmed state."""
        from kiboss.apps.payments.models import Payment

        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.renter != request.user:
            return Response({'error': 'Only the renter can confirm payment'}, status=status.HTTP_403_FORBIDDEN)

        payment, _ = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'amount': booking.total_price,
                'currency': booking.currency,
                'payment_method': 'CREDIT_CARD',
            }
        )

        payment.authorize(payment.amount, {'last_four': '4242', 'brand': 'VISA'})
        payment.hold_in_escrow()

        if booking.status == 'PENDING':
            booking = BookingService.confirm_booking(booking_id=booking.id, actor=request.user)

        booking.payment = payment
        booking.save(update_fields=['payment', 'updated_at'])
        return Response(BookingResponseSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def accept_contract(self, request, pk=None):
        """Record contract acceptance (compatibility endpoint)."""
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        if booking.status == 'PENDING' and booking.payment_id:
            booking = BookingService.confirm_booking(booking_id=booking.id, actor=request.user)

        return Response(BookingResponseSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        """Raise a booking dispute and freeze associated payment."""
        from kiboss.apps.payments.models import Dispute

        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        if not booking.payment_id:
            return Response({'error': 'Cannot dispute booking without payment'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', 'OTHER')
        description = request.data.get('description', '')
        disputed_amount = request.data.get('disputed_amount') or booking.total_price

        dispute, _ = Dispute.objects.get_or_create(
            booking=booking,
            payment=booking.payment,
            defaults={
                'initiated_by': request.user,
                'reason': reason,
                'description': description or 'Dispute opened',
                'disputed_amount': disputed_amount,
            }
        )

        booking.payment.freeze_for_dispute()
        if booking.status != 'DISPUTED':
            booking.transition_to('DISPUTED', actor_type='USER', actor_id=request.user.id, reason='Dispute raised')

        return Response(BookingResponseSerializer(booking).data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get booking timeline events."""
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch booking: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permission
        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            timeline = booking.timeline_events.all().order_by('created_at')
            serializer = BookingTimelineSerializer(timeline, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch timeline: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

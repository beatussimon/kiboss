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
        """List user's bookings (both asset and ride bookings) with optional filtering."""
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        
        role = request.query_params.get('role')
        
        if role == 'RENTER':
            # Asset bookings where user is renter
            asset_queryset = Booking.objects.filter(renter=request.user)
            # Ride bookings where user is passenger
            ride_queryset = SeatBooking.objects.filter(passenger=request.user)
        elif role == 'OWNER':
            # Asset bookings where user owns the asset
            asset_queryset = Booking.objects.filter(asset__owner=request.user)
            # Ride bookings where user is the driver
            ride_queryset = SeatBooking.objects.filter(ride__driver=request.user)
        else:
            # Get bookings where user is renter/passenger or asset owner/driver
            asset_queryset = Booking.objects.filter(renter=request.user) | Booking.objects.filter(asset__owner=request.user)
            ride_queryset = SeatBooking.objects.filter(passenger=request.user) | SeatBooking.objects.filter(ride__driver=request.user)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            asset_queryset = asset_queryset.filter(status=status_filter)
            ride_queryset = ride_queryset.filter(status=status_filter)
        
        # Filter by asset
        asset_id = request.query_params.get('asset_id')
        if asset_id:
            asset_queryset = asset_queryset.filter(asset_id=asset_id)
        
        # Filter by ride
        ride_id = request.query_params.get('ride_id')
        if ride_id:
            ride_queryset = ride_queryset.filter(ride_id=ride_id)
        
        # Optimized querysets with select_related / prefetch_related
        asset_queryset = (
            asset_queryset
            .select_related('asset', 'asset__owner', 'renter')
            .prefetch_related('asset__photos')
            .distinct()
            .order_by('-created_at')
        )
        ride_queryset = (
            ride_queryset
            .select_related('ride', 'ride__driver', 'passenger', 'payment')
            .prefetch_related('ride__photos')
            .distinct()
            .order_by('-created_at')
        )
        
        # Serialize with lightweight list serializers
        from kiboss.apps.bookings.serializers import BookingListResponseSerializer
        from kiboss.apps.rides.serializers import SeatBookingListSerializer
        
        asset_data = BookingListResponseSerializer(asset_queryset, many=True).data
        ride_data = SeatBookingListSerializer(ride_queryset, many=True).data
        
        # Add booking type indicator to each item
        for item in asset_data:
            item['booking_type'] = 'ASSET'
        for item in ride_data:
            item['booking_type'] = 'RIDE'
            # Ensure photos field exists for frontend compatibility
            if 'photos' not in item:
                item['photos'] = []
        
        # Combine and sort by created_at
        combined = asset_data + ride_data
        combined.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return Response(combined)

    @action(detail=False, methods=['get'])
    def incoming(self, request):
        """Get bookings requested on the user's assets AND rides."""
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        from django.db.models import Count, Q
        
        # Optimized querysets with select_related / prefetch_related
        asset_bookings = (
            Booking.objects
            .filter(asset__owner=request.user)
            .select_related('asset', 'asset__owner', 'renter')
            .prefetch_related('asset__photos')
            .order_by('-created_at')
        )
        
        ride_bookings = (
            SeatBooking.objects
            .filter(ride__driver=request.user)
            .select_related('ride', 'ride__driver', 'passenger', 'payment')
            .prefetch_related('ride__photos')
            .order_by('-created_at')
        )
        
        # Serialize with lightweight list serializers
        from kiboss.apps.bookings.serializers import BookingListResponseSerializer
        from kiboss.apps.rides.serializers import SeatBookingListSerializer
        
        asset_data = BookingListResponseSerializer(asset_bookings, many=True).data
        ride_data = SeatBookingListSerializer(ride_bookings, many=True).data
        
        # Add booking type indicator to each item
        for item in asset_data:
            item['booking_type'] = 'ASSET'
        for item in ride_data:
            item['booking_type'] = 'RIDE'
            if 'photos' not in item:
                item['photos'] = []
        
        # Combine and sort by created_at
        combined = asset_data + ride_data
        combined.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        data = combined
        
        # Include 'Plus' insights — batched to avoid N+1 query loop
        if request.user.account_tier in ['PLUS', 'BUSINESS']:
            # Collect unique renter IDs from asset bookings
            renter_ids = {
                item['renter']['id']
                for item in data
                if item.get('booking_type') == 'ASSET' and item.get('renter', {}).get('id')
            }
            # Batch query: one annotated query for all renters
            renter_stats_map = {}
            if renter_ids:
                stats_qs = (
                    Booking.objects
                    .filter(renter_id__in=renter_ids)
                    .values('renter_id')
                    .annotate(
                        total_bookings=Count('id'),
                        completed_bookings=Count('id', filter=Q(status='COMPLETED')),
                        cancelled_bookings=Count('id', filter=Q(status='CANCELLED')),
                    )
                )
                for row in stats_qs:
                    renter_stats_map[str(row['renter_id'])] = {
                        'total_bookings': row['total_bookings'],
                        'completed_bookings': row['completed_bookings'],
                        'cancelled_bookings': row['cancelled_bookings'],
                    }

            # Collect unique passenger IDs from ride bookings
            passenger_ids = {
                item['passenger']['id']
                for item in data
                if item.get('booking_type') == 'RIDE' and item.get('passenger', {}).get('id')
            }
            passenger_stats_map = {}
            if passenger_ids:
                stats_qs = (
                    SeatBooking.objects
                    .filter(passenger_id__in=passenger_ids)
                    .values('passenger_id')
                    .annotate(
                        total_bookings=Count('id'),
                        completed_bookings=Count('id', filter=Q(status='COMPLETED')),
                        cancelled_bookings=Count('id', filter=Q(status='CANCELLED')),
                    )
                )
                for row in stats_qs:
                    passenger_stats_map[str(row['passenger_id'])] = {
                        'total_bookings': row['total_bookings'],
                        'completed_bookings': row['completed_bookings'],
                        'cancelled_bookings': row['cancelled_bookings'],
                    }

            # Attach stats from pre-computed maps (O(1) lookup per booking)
            for item in data:
                if item.get('booking_type') == 'ASSET':
                    renter_id = item.get('renter', {}).get('id')
                    if renter_id and str(renter_id) in renter_stats_map:
                        stats = renter_stats_map[str(renter_id)]
                        stats['member_since'] = item.get('renter', {}).get('created_at')
                        item['renter_stats'] = stats
                    else:
                        item['renter_stats'] = None
                else:
                    passenger_id = item.get('passenger', {}).get('id')
                    if passenger_id and str(passenger_id) in passenger_stats_map:
                        stats = passenger_stats_map[str(passenger_id)]
                        stats['member_since'] = item.get('passenger', {}).get('created_at')
                        item['passenger_stats'] = stats
                    else:
                        item['passenger_stats'] = None
                    item['renter_stats'] = None
        
        return Response(data)

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
        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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

    @action(detail=False, methods=['get'])
    def calculate_price(self, request):
        """Calculate the price for a potential booking."""
        asset_id = request.query_params.get('asset_id')
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        quantity = int(request.query_params.get('quantity', 1))

        if not all([asset_id, start_time_str, end_time_str]):
            return Response(
                {'error': 'asset_id, start_time, and end_time are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from dateutil.parser import parse
        try:
            start_time = parse(start_time_str)
            end_time = parse(end_time_str)
        except Exception:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            price_breakdown = BookingService.calculate_price(
                asset_id=asset_id,
                quantity=quantity,
                start_time=start_time,
                end_time=end_time
            )
            return Response(price_breakdown)
        except Exception as e:
            logger.exception("Error calculating price")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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

        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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
        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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

        if payment.status == 'PENDING':
            payment.authorize(payment.amount, {'last_four': '4242', 'brand': 'VISA'})
            payment.hold_in_escrow()

        # Remove the automatic confirm_booking call so owners can approve manually.

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

        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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

        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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
        if booking.renter != request.user and booking.asset.owner != request.user and not request.user.is_staff:
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

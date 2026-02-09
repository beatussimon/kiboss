"""
Views for KIBOSS Booking API
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from kiboss.apps.bookings.models import Booking
from kiboss.apps.bookings.serializers import (
    BookingCreateSerializer, BookingResponseSerializer,
    BookingListSerializer, BookingUpdateSerializer,
    BookingCancelSerializer, BookingCompleteSerializer, BookingTimelineSerializer
)
from kiboss.apps.bookings.services import BookingService, BookingError
from kiboss.apps.rbac.permissions import RoleBasedPermission

logger = logging.getLogger(__name__)


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
    
    permission_classes = [RoleBasedPermission]
    required_permission = 'BOOKING_VIEW'
    
    def list(self, request):
        """List user's bookings with optional filtering."""
        # Get bookings where user is renter or asset owner
        as_renter = Booking.objects.filter(renter=request.user)
        as_owner = Booking.objects.filter(asset__owner=request.user)
        queryset = as_renter | as_owner
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by asset
        asset_id = request.query_params.get('asset_id')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        queryset = queryset.order_by('-created_at')
        serializer = BookingListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get booking details."""
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
                notes=serializer.validated_data.get('notes', '')
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
        
        # Check permission
        if booking.renter != request.user and booking.asset.owner != request.user:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        timeline = booking.timeline_events.all().order_by('created_at')
        serializer = BookingTimelineSerializer(timeline, many=True)
        return Response(serializer.data)

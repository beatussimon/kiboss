"""
Views for Rides API - Ride-Sharing Module
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from kiboss.apps.rides.models import Ride, RideStop, SeatBooking, RideSchedule
from kiboss.apps.rides.serializers import (
    RideSerializer, RideStopSerializer, SeatBookingSerializer,
    RideScheduleSerializer, RideListSerializer, SeatBookingCreateSerializer
)
from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError


class RideViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing rides.
    
    Provides CRUD operations and custom actions for ride-sharing.
    """
    queryset = Ride.objects.select_related('driver', 'vehicle_asset').order_by('-departure_time')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RideListSerializer
        return RideSerializer
    
    def perform_create(self, serializer):
        """Set the driver to the current user when creating a ride."""
        serializer.save(driver=self.request.user)
    
    def get_queryset(self):
        queryset = Ride.objects.select_related('driver', 'vehicle_asset').prefetch_related('stops').order_by('-departure_time')
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by driver
        driver_id = self.request.query_params.get('driver')
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        
        # Filter by origin/destination
        origin = self.request.query_params.get('origin')
        if origin:
            queryset = queryset.filter(origin__icontains=origin)
        
        destination = self.request.query_params.get('destination')
        if destination:
            queryset = queryset.filter(destination__icontains=destination)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(departure_time__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(departure_time__date__lte=date_to)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_stop(self, request, pk=None):
        """Add a stop to a ride."""
        ride = self.get_object()
        serializer = RideStopSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(ride=ride)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def stops(self, request, pk=None):
        """Get all stops for a ride."""
        ride = self.get_object()
        stops = ride.stops.all().order_by('stop_order')
        serializer = RideStopSerializer(stops, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def available_seats(self, request, pk=None):
        """Get available seats count for a ride."""
        ride = self.get_object()
        available = ride.get_available_seats()
        return Response({
            'available_seats': available,
            'total_seats': ride.total_seats,
            'confirmed_seats': ride.confirmed_seats
        })
    
    @action(detail=True, methods=['get'])
    def seats_detail(self, request, pk=None):
        """Get detailed seat availability with individual seat status."""
        ride = self.get_object()
        available = ride.get_available_seats()
        
        # Get all bookings for this ride
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        bookings = SeatBooking.objects.filter(
            ride=ride,
            status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
        ).values('seat_number', 'status', 'id')
        
        # Build seat status map
        booked_seats = {b['seat_number']: {'status': b['status'], 'booking_id': str(b['id'])} for b in bookings}
        
        # Build seat list
        seats = []
        for seat_num in range(1, ride.total_seats + 1):
            if seat_num in booked_seats:
                status = 'BOOKED' if booked_seats[seat_num]['status'] == SeatBookingStatus.CONFIRMED else 'BLOCKED'
                seats.append({
                    'seat_number': seat_num,
                    'status': status,
                    'price': str(ride.seat_price),
                    'booking_id': booked_seats[seat_num]['booking_id']
                })
            else:
                seats.append({
                    'seat_number': seat_num,
                    'status': 'AVAILABLE',
                    'price': str(ride.seat_price)
                })
        
        return Response({
            'ride_id': str(ride.id),
            'total_seats': ride.total_seats,
            'available_seats': available,
            'seats': seats
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a ride (driver only)."""
        ride = self.get_object()
        ride.status = 'CANCELLED'
        ride.save()
        serializer = self.get_serializer(ride)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        """Book a seat on this ride."""
        ride = self.get_object()
        
        # Get seat number from request
        seat_number = request.data.get('seat_number')
        if not seat_number:
            return Response(
                {'error': 'seat_number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get other optional fields
        pickup_stop_id = request.data.get('pickup_stop_id')
        dropoff_stop_id = request.data.get('dropoff_stop_id')
        passenger_notes = request.data.get('passenger_notes', '')
        luggage_count = request.data.get('luggage_count', 0)
        
        # Import here to avoid circular imports
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError
        
        # Acquire Redis lock for seat booking
        lock_key = f"lock:ride:{ride.id}:seat:{seat_number}"
        lock_manager = get_lock_manager()
        
        try:
            with lock_manager.lock(lock_key, ttl=30, max_retries=3):
                # Check if seat is available
                existing = SeatBooking.objects.filter(
                    ride=ride,
                    seat_number=seat_number,
                    status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
                ).exists()
                
                if existing:
                    return Response(
                        {'error': f'Seat {seat_number} is already taken'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check ride is still available
                if ride.is_full():
                    return Response(
                        {'error': 'Ride is fully booked'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create the booking
                with transaction.atomic():
                    booking = SeatBooking.objects.create(
                        ride=ride,
                        passenger=request.user,
                        seat_number=seat_number,
                        status=SeatBookingStatus.RESERVED,
                        price=ride.seat_price,
                        currency=ride.currency,
                        pickup_stop_id=pickup_stop_id,
                        dropoff_stop_id=dropoff_stop_id,
                        passenger_notes=passenger_notes,
                        luggage_count=luggage_count
                    )
                    
                    # Update ride seat counts
                    ride.reserved_seats += 1
                    ride.save(update_fields=['reserved_seats', 'updated_at'])
                
                response_serializer = SeatBookingSerializer(booking)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
        except LockAcquisitionError:
            return Response(
                {'error': 'Unable to process booking. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class RideStopViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ride stops.
    """
    queryset = RideStop.objects.all().order_by('stop_order')
    serializer_class = RideStopSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = RideStop.objects.all().order_by('stop_order')
        
        ride_id = self.request.query_params.get('ride')
        if ride_id:
            queryset = queryset.filter(ride_id=ride_id)
        
        stop_type = self.request.query_params.get('stop_type')
        if stop_type:
            queryset = queryset.filter(stop_type=stop_type)
        
        return queryset


class SeatBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing seat bookings.
    """
    queryset = SeatBooking.objects.select_related('ride', 'passenger', 'pickup_stop', 'dropoff_stop').order_by('-created_at')
    serializer_class = SeatBookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SeatBookingSerializer
        return SeatBookingSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create a seat booking with Redis locking to prevent overbooking.
        """
        serializer = SeatBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        ride = serializer.validated_data['ride']
        seat_number = serializer.validated_data['seat_number']
        
        # Acquire Redis lock for seat booking
        lock_key = f"lock:ride:{ride.id}:seat:{seat_number}"
        lock_manager = get_lock_manager()
        
        try:
            with lock_manager.lock(lock_key, ttl=30, max_retries=3):
                # Re-validate seat availability inside lock
                from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
                
                existing = SeatBooking.objects.filter(
                    ride=ride,
                    seat_number=seat_number,
                    status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
                ).exists()
                
                if existing:
                    return Response(
                        {'error': f'Seat {seat_number} is already taken'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check ride is still available
                if ride.is_full():
                    return Response(
                        {'error': 'Ride is fully booked'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create the booking
                with transaction.atomic():
                    booking = SeatBooking.objects.create(
                        ride=ride,
                        passenger=request.user,
                        seat_number=seat_number,
                        status=SeatBookingStatus.RESERVED,
                        price=ride.seat_price,
                        currency=ride.currency,
                        pickup_stop_id=serializer.validated_data.get('pickup_stop_id'),
                        dropoff_stop_id=serializer.validated_data.get('dropoff_stop_id'),
                        passenger_notes=serializer.validated_data.get('passenger_notes', ''),
                        luggage_count=serializer.validated_data.get('luggage_count', 0)
                    )
                    
                    # Update ride seat counts
                    ride.reserved_seats += 1
                    ride.save(update_fields=['reserved_seats', 'updated_at'])
                
                response_serializer = SeatBookingSerializer(booking)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
        except LockAcquisitionError:
            return Response(
                {'error': 'Unable to process booking. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    def get_queryset(self):
        queryset = SeatBooking.objects.select_related('ride', 'passenger', 'pickup_stop', 'dropoff_stop', 'payment').order_by('-created_at')
        
        # Filter by passenger
        passenger_id = self.request.query_params.get('passenger')
        if passenger_id:
            queryset = queryset.filter(passenger_id=passenger_id)
        
        # Filter by ride
        ride_id = self.request.query_params.get('ride')
        if ride_id:
            queryset = queryset.filter(ride_id=ride_id)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a seat booking."""
        booking = self.get_object()
        reason = request.data.get('reason', '')
        booking.cancel(reason=reason)
        serializer = self.get_serializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Check in for a seat booking."""
        booking = self.get_object()
        booking.checked_in_at = timezone.now()
        booking.save()
        serializer = self.get_serializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def board(self, request, pk=None):
        """Mark passenger as boarded."""
        booking = self.get_object()
        booking.boarded_at = timezone.now()
        booking.status = 'BOARDED'
        booking.save()
        serializer = self.get_serializer(booking)
        return Response(serializer.data)


class RideScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ride schedules.
    """
    queryset = RideSchedule.objects.all().order_by('-created_at')
    serializer_class = RideScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = RideSchedule.objects.all().order_by('-created_at')
        
        driver_id = self.request.query_params.get('driver')
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def generate_rides(self, request, pk=None):
        """Generate rides from schedule."""
        schedule = self.get_object()
        days_ahead = int(request.data.get('days_ahead', 30))
        rides = schedule.generate_rides(days_ahead=days_ahead)
        serializer = RideSerializer(rides, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

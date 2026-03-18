"""
Views for Rides API - Ride-Sharing Module
"""
from rest_framework import viewsets, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from kiboss.apps.rides.models import Ride, RideStop, SeatBooking, RideSchedule, RidePhoto
from kiboss.apps.rides.serializers import (
    RideSerializer, RideStopSerializer, SeatBookingSerializer,
    RideScheduleSerializer, RideListSerializer, SeatBookingCreateSerializer
)
from kiboss.apps.assets.models import Asset, AssetType, VerificationStatus, AssetDocument
from kiboss.apps.assets.serializers import AssetSerializer
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskPriority, TaskStatus
from django.contrib.contenttypes.models import ContentType
from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError
from kiboss.apps.users.models import CorporateWorker
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.db.models import Count, Q


class VehicleRegistrationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for vehicle registration and verification submission.
    """
    queryset = Asset.objects.filter(asset_type=AssetType.VEHICLE)
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser] # Explicit parsers

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Register a vehicle and submit for verification.
        """
        # 1. Create the Asset (Vehicle)
        data = request.data.copy()
        
        # Ensure correct asset type and owner
        data['asset_type'] = AssetType.VEHICLE
        # Force pending status initially
        data['verification_status'] = VerificationStatus.PENDING
        
        serializer = AssetSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Check if user has a verified corporate profile
        is_verified_corporate = False
        if hasattr(request.user, 'corporate_profile') and request.user.corporate_profile.verification_status == 'VERIFIED':
            is_verified_corporate = True
            
        if not is_verified_corporate:
            # Regular users are limited by their tier.
            # Free: 3 total assets max. Plus: 10 total assets max, 2 vehicles max.
            total_assets = Asset.objects.filter(
                owner=request.user, 
                is_active=True,
                parent__isnull=True
            ).count()
            
            if request.user.account_tier == 'FREE' and total_assets >= 3:
                raise PermissionDenied("Your Free plan allows up to 3 active assets in total. Upgrade to Plus to add more.")
            elif request.user.account_tier == 'PLUS':
                if total_assets >= 10:
                    raise PermissionDenied("Your Plus plan allows up to 10 active assets in total.")
                
                vehicle_count = Asset.objects.filter(
                    owner=request.user, 
                    asset_type=AssetType.VEHICLE,
                    is_active=True,
                    parent__isnull=True
                ).count()
                
                if vehicle_count >= 2:
                    raise PermissionDenied("Your Plus plan allows a maximum of 2 active vehicles.")        
        with transaction.atomic():
            asset = serializer.save(
                owner=request.user, 
                asset_type=AssetType.VEHICLE, 
                verification_status=VerificationStatus.PENDING,
                is_corporate=is_verified_corporate,
                is_listed=False,
                is_active=True
            )
            
            # 2. Handle documents
            # Support multiple files with 'documents' key
            files = request.FILES.getlist('documents')
            # Support optional document_types list matching files
            doc_types = request.data.getlist('document_types') if hasattr(request.data, 'getlist') else []
            
            for i, file in enumerate(files):
                doc_type = doc_types[i] if i < len(doc_types) else 'OTHER'
                AssetDocument.objects.create(
                    asset=asset,
                    document_type=doc_type,
                    file=file,
                    name=file.name
                )
                
            # 3. Create StaffTask for verification using the new service
            from kiboss.apps.common.services import VerificationService
            try:
                VerificationService.request_verification(asset, request.user)
            except Exception as e:
                # Log error but don't fail the registration completely?
                # Ideally, we should rollback if task creation fails, which atomic block handles.
                raise e
            
            # 4. If any photos were uploaded, add them
            photos = request.FILES.getlist('photos')
            for i, photo in enumerate(photos):
                from kiboss.apps.assets.models import AssetPhoto
                AssetPhoto.objects.create(
                    asset=asset,
                    image=photo,
                    order=i,
                    is_primary=(i == 0)
                )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='submit_verification')
    def submit_verification(self, request, pk=None):
        """
        Submit an existing vehicle for verification.
        """
        try:
            asset = self.get_object()
        except Exception:
            return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if asset.verification_status == VerificationStatus.VERIFIED:
            return Response({'error': 'Vehicle is already verified'}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            # Use the service to request verification
            from kiboss.apps.common.services import VerificationService
            VerificationService.request_verification(asset, request.user)
            
        return Response({'status': 'Verification submitted'})


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
        """
        Set the driver to the current user and enforce fleet rules for BUSINESS rides.
        """
        user = self.request.user
        ride_type = serializer.validated_data.get('ride_type', 'PERSONAL')
        
        if user.is_staff and not user.is_superuser:
            raise PermissionDenied("Staff accounts cannot offer rides. Use a personal account or request superadmin access.")
        
        # Enforce Ride Limits
        if ride_type != 'BUSINESS':
            if user.account_tier == 'FREE':
                active_rides = Ride.objects.filter(
                    driver=user, status__in=['SCHEDULED', 'OPEN']
                ).count()
                if active_rides >= 3:
                    raise PermissionDenied("Your Free plan allows up to 3 active/scheduled rides. Please upgrade to Plus to offer more.")
            elif user.account_tier == 'PLUS':
                from django.utils import timezone
                current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                monthly_rides = Ride.objects.filter(
                    driver=user,
                    created_at__gte=current_month
                ).count()
                if monthly_rides >= 100:
                    raise PermissionDenied("Your Plus plan allows up to 100 rides per month. You've reached your limit.")
        
        # Check Business Isolation: ASSET businesses cannot offer rides
        if hasattr(user, 'corporate_profile'):
            if user.corporate_profile.business_category == 'ASSET':
                raise PermissionDenied("Asset businesses cannot offer rides. Register an individual or Ride Business account.")
            
            # Corporate Ride accounts constraints
            if user.corporate_profile.verification_status == 'VERIFIED' and user.account_tier == 'BUSINESS':
                if ride_type == 'PERSONAL':
                    raise PermissionDenied("Corporate Ride accounts can only offer BUSINESS rides. Switch to a personal account to offer personal rides.")
        
        # Check if user has at least one verified vehicle asset
        has_verified_vehicle = Asset.objects.filter(
            owner=user,
            asset_type=AssetType.VEHICLE,
            verification_status=VerificationStatus.VERIFIED
        ).exists()
        
        if not has_verified_vehicle and not user.is_superuser:
            raise DRFValidationError({
                'error': 'Vehicle verification required',
                'message': 'You must have a verified vehicle to offer a ride. Please register your vehicle first.'
            })
        
        extra_kwargs = {'driver': user}
        
        # FLEET ENFORCEMENT for BUSINESS rides
        if ride_type == 'BUSINESS':
            if not hasattr(user, 'corporate_profile') or user.corporate_profile.verification_status != 'VERIFIED':
                raise PermissionDenied("Only verified corporate ride businesses can create business rides.")
            
            if user.account_tier != 'BUSINESS':
                raise PermissionDenied("Your business subscription is inactive/expired. Please renew to offer business rides.")
            
            # Vehicle must belong to the corporate fleet
            vehicle_asset = serializer.validated_data.get('vehicle_asset')
            if vehicle_asset:
                if vehicle_asset.owner != user:
                    raise PermissionDenied("Vehicle must be from your corporate fleet.")
                if vehicle_asset.verification_status != VerificationStatus.VERIFIED:
                    raise DRFValidationError({'vehicle_asset': 'Vehicle must be verified before dispatching a trip.'})
            
            # If assigned_driver is specified, validate it's a DRIVER worker on this profile
            assigned_driver_id = self.request.data.get('assigned_driver')
            if assigned_driver_id:
                try:
                    worker = CorporateWorker.objects.get(
                        id=assigned_driver_id,
                        corporate_profile=user.corporate_profile,
                        role='DRIVER',
                        status='ACTIVE'
                    )
                    extra_kwargs['assigned_driver'] = worker
                except CorporateWorker.DoesNotExist:
                    raise DRFValidationError({'assigned_driver': 'Invalid or inactive driver.'})
        
        serializer.save(**extra_kwargs)
    
    def get_queryset(self):
        from kiboss.apps.rides.models import RideStatus
        queryset = Ride.objects.select_related('driver', 'vehicle_asset').prefetch_related('stops').order_by('-departure_time')
        
        # Filter by driver
        driver_id = self.request.query_params.get('driver')
        is_own_rides = False
        if driver_id == 'me':
            queryset = queryset.filter(driver=self.request.user)
            is_own_rides = True
        elif driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        elif not is_own_rides:
            # Default: exclude FULL and CANCELLED rides from public listings
            # Users can still see their own FULL rides (they'll be handled above)
            queryset = queryset.exclude(status__in=[RideStatus.FULL, RideStatus.CANCELLED])
        
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

        # Filter by ride_type / context
        ride_type_param = self.request.query_params.get('ride_type')
        if ride_type_param:
            queryset = queryset.filter(ride_type=ride_type_param)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def fleet_stats(self, request):
        """Get fleet statistics for the current corporate user."""
        user = request.user
        if not hasattr(user, 'corporate_profile') or user.corporate_profile.verification_status != 'VERIFIED':
            return Response({'error': 'Verified corporate profile required.'}, status=status.HTTP_403_FORBIDDEN)
        
        # Vehicle count (verified fleet)
        vehicle_count = Asset.objects.filter(
            owner=user,
            asset_type=AssetType.VEHICLE,
            verification_status=VerificationStatus.VERIFIED
        ).count()
        
        # Active trips (SCHEDULED, OPEN, DEPARTED, IN_TRANSIT)
        active_trips = Ride.objects.filter(
            driver=user,
            ride_type='BUSINESS',
            status__in=['SCHEDULED', 'OPEN', 'DEPARTED', 'IN_TRANSIT']
        ).count()
        
        # Completed trips (all time)
        completed_trips = Ride.objects.filter(
            driver=user,
            ride_type='BUSINESS',
            status='COMPLETED'
        ).count()
        
        # Total completed seat bookings across all trips
        total_passengers = SeatBooking.objects.filter(
            ride__driver=user,
            ride__ride_type='BUSINESS',
            status='COMPLETED'
        ).count()
        
        # Active drivers from CorporateWorker
        driver_count = CorporateWorker.objects.filter(
            corporate_profile=user.corporate_profile,
            role='DRIVER',
            status='ACTIVE'
        ).count()
        
        return Response({
            'vehicle_count': vehicle_count,
            'active_trips': active_trips,
            'completed_trips': completed_trips,
            'total_passengers': total_passengers,
            'driver_count': driver_count,
        })
    
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
    def upload_photos(self, request, pk=None):
        """Upload photos for a ride."""
        ride = self.get_object()
        
        # Check if user is the driver
        if ride.driver_id != request.user.id and not request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only the ride driver can upload photos')
        
        # Get uploaded files
        files = request.FILES.getlist('images')
        if not files:
            # Try single file upload
            single_file = request.FILES.get('image')
            if single_file:
                files = [single_file]
            else:
                from rest_framework.response import Response
                from rest_framework import status
                return Response(
                    {'error': 'No images provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if is_primary is specified
        is_primary = request.data.get('is_primary', 'false').lower() == 'true'
        
        created_photos = []
        current_order = ride.photos.count()
        
        for i, file in enumerate(files[:10]):  # Max 10 images per upload
            photo = RidePhoto.objects.create(
                ride=ride,
                image=file,
                order=current_order + i,
                is_primary=(is_primary and i == 0) or (current_order == 0 and i == 0)
            )
            created_photos.append(photo)
        
        from kiboss.apps.rides.serializers import RidePhotoSerializer
        serializer = RidePhotoSerializer(created_photos, many=True)
        from rest_framework.response import Response
        from rest_framework import status
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        """Book a seat on this ride."""
        ride = self.get_object()
        
        # Prevent self-booking
        if ride.driver == request.user:
            return Response(
                {'error': 'You cannot book a seat on your own ride'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
                    locked_ride = Ride.objects.select_for_update().get(id=ride.id)
                    booking = SeatBooking.objects.create(
                        ride=locked_ride,
                        passenger=request.user,
                        seat_number=seat_number,
                        status=SeatBookingStatus.RESERVED,
                        price=locked_ride.seat_price,
                        currency=locked_ride.currency,
                        pickup_stop_id=pickup_stop_id,
                        dropoff_stop_id=dropoff_stop_id,
                        passenger_notes=passenger_notes,
                        luggage_count=luggage_count
                    )
                    
                    # Update ride seat counts
                    locked_ride.reserved_seats += 1
                    locked_ride.save(update_fields=['reserved_seats', 'updated_at'])
                
                # Send notifications to driver and passenger
                try:
                    from kiboss.apps.notifications.services import NotificationService
                    NotificationService.notify_seat_booking_created(booking)
                except Exception as e:
                    # Log error but don't fail the booking
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send notification for seat booking: {e}")
                
                response_serializer = SeatBookingSerializer(booking)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
        except LockAcquisitionError:
            return Response(
                {'error': 'Unable to process booking. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    @action(detail=True, methods=['post'])
    def bulk_book_seats(self, request, pk=None):
        """Book multiple seats on this ride for Business Rides."""
        ride = self.get_object()
        
        # Prevent self-booking
        if ride.driver == request.user:
            return Response(
                {'error': 'You cannot book seats on your own ride'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        quantity = int(request.data.get('quantity', 1))
        if quantity <= 0:
            return Response({'error': 'Quantity must be at least 1'}, status=status.HTTP_400_BAD_REQUEST)
            
        pickup_stop_id = request.data.get('pickup_stop_id')
        dropoff_stop_id = request.data.get('dropoff_stop_id')
        passenger_notes = request.data.get('passenger_notes', '')
        luggage_count = request.data.get('luggage_count', 0)
        
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError
        
        lock_key = f"lock:ride:{ride.id}:bulk_book"
        lock_manager = get_lock_manager()
        
        try:
            with lock_manager.lock(lock_key, ttl=30, max_retries=3):
                # Check ride is still available
                if ride.is_full() or ride.get_available_seats() < quantity:
                    return Response(
                        {'error': f'Not enough available seats. Only {ride.get_available_seats()} left.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
                # Find available seats
                existing_bookings = SeatBooking.objects.filter(
                    ride=ride,
                    status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
                ).values_list('seat_number', flat=True)
                
                available_seat_numbers = [i for i in range(1, ride.total_seats + 1) if i not in existing_bookings]
                
                if len(available_seat_numbers) < quantity:
                    return Response(
                        {'error': 'Not enough available seats simultaneously.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
                seats_to_book = available_seat_numbers[:quantity]
                
                # Create the bookings
                created_bookings = []
                with transaction.atomic():
                    locked_ride = Ride.objects.select_for_update().get(id=ride.id)
                    for seat_number in seats_to_book:
                        booking = SeatBooking.objects.create(
                            ride=locked_ride,
                            passenger=request.user,
                            seat_number=seat_number,
                            status=SeatBookingStatus.RESERVED,
                            price=locked_ride.seat_price,
                            currency=locked_ride.currency,
                            pickup_stop_id=pickup_stop_id,
                            dropoff_stop_id=dropoff_stop_id,
                            passenger_notes=passenger_notes,
                            luggage_count=luggage_count
                        )
                        created_bookings.append(booking)
                    
                    # Update ride seat counts
                    locked_ride.reserved_seats += quantity
                    locked_ride.save(update_fields=['reserved_seats', 'updated_at'])
                
                # Send notifications to driver and passenger
                try:
                    from kiboss.apps.notifications.services import NotificationService
                    for booking in created_bookings:
                        NotificationService.notify_seat_booking_created(booking)
                except Exception as e:
                    # Log error but don't fail the booking
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send notification for bulk seat booking: {e}")
                
                response_serializer = SeatBookingSerializer(created_bookings, many=True)
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
        
        if ride.driver == request.user:
            return Response(
                {'error': 'You cannot book a seat on your own ride'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
                    locked_ride = Ride.objects.select_for_update().get(id=ride.id)
                    booking = SeatBooking.objects.create(
                        ride=locked_ride,
                        passenger=request.user,
                        seat_number=seat_number,
                        status=SeatBookingStatus.RESERVED,
                        price=locked_ride.seat_price,
                        currency=locked_ride.currency,
                        pickup_stop_id=serializer.validated_data.get('pickup_stop_id'),
                        dropoff_stop_id=serializer.validated_data.get('dropoff_stop_id'),
                        passenger_notes=serializer.validated_data.get('passenger_notes', ''),
                        luggage_count=serializer.validated_data.get('luggage_count', 0)
                    )
                    
                    # Update ride seat counts
                    locked_ride.reserved_seats += 1
                    locked_ride.save(update_fields=['reserved_seats', 'updated_at'])
                
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
        if passenger_id == 'me':
            queryset = queryset.filter(passenger=self.request.user)
        elif passenger_id:
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

from kiboss.apps.rides.models import CargoBooking

class CargoBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cargo bookings.
    """
    queryset = CargoBooking.objects.select_related('ride', 'sender', 'pickup_stop', 'dropoff_stop').order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from kiboss.apps.rides.serializers import CargoBookingSerializer, CargoBookingCreateSerializer
        if self.action == 'create':
            return CargoBookingCreateSerializer
        return CargoBookingSerializer
        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        ride = serializer.validated_data['ride']
        weight = serializer.validated_data['weight']
        
        if ride.driver == request.user:
            return Response(
                {'error': 'You cannot book cargo on your own ride'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        from kiboss.apps.common.locking import get_lock_manager, LockAcquisitionError
        lock_key = f"lock:ride:{ride.id}:cargo"
        lock_manager = get_lock_manager()
        
        try:
            with lock_manager.lock(lock_key, ttl=30, max_retries=3):
                # Re-validate
                if ride.get_available_cargo() < weight:
                    return Response(
                        {'error': f'Not enough available cargo capacity. Only {ride.get_available_cargo()} kg available.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
                with transaction.atomic():
                    from kiboss.apps.rides.models import CargoBooking, CargoBookingStatus
                    booking = CargoBooking.objects.create(
                        ride=ride,
                        sender=request.user,
                        weight=weight,
                        status=CargoBookingStatus.RESERVED,
                        price=ride.cargo_price * weight, # simple calculation
                        currency=ride.currency,
                        pickup_stop_id=serializer.validated_data.get('pickup_stop_id'),
                        dropoff_stop_id=serializer.validated_data.get('dropoff_stop_id'),
                        cargo_description=serializer.validated_data.get('cargo_description', ''),
                        recipient_name=serializer.validated_data.get('recipient_name', ''),
                        recipient_phone=serializer.validated_data.get('recipient_phone', '')
                    )
                    
                    ride.reserved_cargo += weight
                    ride.save(update_fields=['reserved_cargo', 'updated_at'])
                    
                from kiboss.apps.rides.serializers import CargoBookingSerializer
                response_serializer = CargoBookingSerializer(booking)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
        except LockAcquisitionError:
            return Response(
                {'error': 'Unable to process cargo booking.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by sender
        sender_id = self.request.query_params.get('sender')
        if sender_id == 'me':
            queryset = queryset.filter(sender=self.request.user)
        elif sender_id:
            queryset = queryset.filter(sender_id=sender_id)
            
        # Filter by ride
        ride_id = self.request.query_params.get('ride')
        if ride_id:
            queryset = queryset.filter(ride_id=ride_id)
            
        return queryset
        
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get('reason', '')
        booking.cancel(reason=reason)
        serializer = self.get_serializer(booking)
        return Response(serializer.data)

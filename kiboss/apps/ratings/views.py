"""
Views for Ratings API
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction, models
from django.utils import timezone
from kiboss.apps.ratings.models import Rating, RatingCategory, RatingStatus
from kiboss.apps.ratings.serializers import RatingSerializer, RatingCreateSerializer
from kiboss.apps.bookings.models import Booking


class RatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ratings.
    """
    queryset = Rating.objects.all().order_by('-created_at')
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Rating.objects.select_related(
            'booking', 'booking__asset', 'reviewer', 'reviewee'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', RatingStatus.APPROVED)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by user (as reviewer or reviewee)
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(models.Q(reviewer_id=user_id) | models.Q(reviewee_id=user_id))
            
        # Specific filter for reviewee (for profile pages)
        reviewee_id = self.request.query_params.get('reviewee')
        if reviewee_id:
            queryset = queryset.filter(reviewee_id=reviewee_id)
        
        # NEW: filter by asset
        asset_id = self.request.query_params.get('asset')
        if asset_id:
            queryset = queryset.filter(booking__asset_id=asset_id)
        
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new rating."""
        serializer = RatingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        booking_id = serializer.validated_data.get('booking_id')
        ride_id = serializer.validated_data.get('ride_id')
        
        # Get booking or ride
        booking = None
        ride = None
        cargo_ride = None
        
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                return Response(
                    {'error': 'Booking not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Determine reviewee and validation based on category
        category = serializer.validated_data['category']
        reviewee = None
        
        if category == RatingCategory.RENTER_TO_OWNER:
            if not booking:
                return Response({'error': 'booking_id required for RENTER_TO_OWNER rating'}, status=status.HTTP_400_BAD_REQUEST)
            if booking.renter != request.user:
                return Response({'error': 'Only the renter can leave this review'}, status=status.HTTP_403_FORBIDDEN)
            if booking.status != 'COMPLETED':
                return Response({'error': 'Can only rate after booking is completed'}, status=status.HTTP_400_BAD_REQUEST)
            reviewee = booking.asset.owner
        elif category == RatingCategory.OWNER_TO_RENTER:
            if not booking:
                return Response({'error': 'booking_id required for OWNER_TO_RENTER rating'}, status=status.HTTP_400_BAD_REQUEST)
            if booking.asset.owner != request.user:
                return Response({'error': 'Only the asset owner can leave this review'}, status=status.HTTP_403_FORBIDDEN)
            if booking.status != 'COMPLETED':
                return Response({'error': 'Can only rate after booking is completed'}, status=status.HTTP_400_BAD_REQUEST)
            reviewee = booking.renter
        elif category == RatingCategory.PASSENGER_TO_DRIVER:
            if not ride_id:
                return Response({'error': 'ride_id required for PASSENGER_TO_DRIVER rating'}, status=status.HTTP_400_BAD_REQUEST)
            from kiboss.apps.rides.models import SeatBooking, CargoBooking
            # Try SeatBooking first
            ride_booking = SeatBooking.objects.filter(id=ride_id).first()
            if ride_booking:
                if ride_booking.passenger != request.user:
                    return Response({'error': 'Only the passenger can leave this review'}, status=status.HTTP_403_FORBIDDEN)
                if ride_booking.ride.status != 'COMPLETED':
                    return Response({'error': 'Can only rate after ride is completed'}, status=status.HTTP_400_BAD_REQUEST)
                reviewee = ride_booking.ride.driver
                ride = ride_booking
            else:
                # Try CargoBooking
                cargo_booking = CargoBooking.objects.filter(id=ride_id).first()
                if cargo_booking:
                    if cargo_booking.sender != request.user:
                        return Response({'error': 'Only the sender can leave this review'}, status=status.HTTP_403_FORBIDDEN)
                    if cargo_booking.ride.status != 'COMPLETED':
                        return Response({'error': 'Can only rate after cargo is delivered (ride completed)'}, status=status.HTTP_400_BAD_REQUEST)
                    reviewee = cargo_booking.ride.driver
                    cargo_ride = cargo_booking
                else:
                    return Response({'error': 'Ride booking not found'}, status=status.HTTP_404_NOT_FOUND)

        elif category == RatingCategory.DRIVER_TO_PASSENGER:
            if not ride_id:
                return Response({'error': 'ride_id required for DRIVER_TO_PASSENGER rating'}, status=status.HTTP_400_BAD_REQUEST)
            from kiboss.apps.rides.models import SeatBooking, CargoBooking
            # Try SeatBooking first
            ride_booking = SeatBooking.objects.filter(id=ride_id).first()
            if ride_booking:
                if ride_booking.ride.driver != request.user:
                    return Response({'error': 'Only the driver can leave this review'}, status=status.HTTP_403_FORBIDDEN)
                if ride_booking.ride.status != 'COMPLETED':
                    return Response({'error': 'Can only rate after ride is completed'}, status=status.HTTP_400_BAD_REQUEST)
                reviewee = ride_booking.passenger
                ride = ride_booking
            else:
                # Try CargoBooking
                cargo_booking = CargoBooking.objects.filter(id=ride_id).first()
                if cargo_booking:
                    if cargo_booking.ride.driver != request.user:
                        return Response({'error': 'Only the driver can leave this review'}, status=status.HTTP_403_FORBIDDEN)
                    if cargo_booking.ride.status != 'COMPLETED':
                        return Response({'error': 'Can only rate after cargo is delivered (ride completed)'}, status=status.HTTP_400_BAD_REQUEST)
                    reviewee = cargo_booking.sender
                    cargo_ride = cargo_booking
                else:
                    return Response({'error': 'Ride booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if not reviewee:
            return Response({'error': 'Could not determine reviewee'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already rated this booking/ride
        filter_kwargs = {'reviewer': request.user}
        if booking:
            filter_kwargs['booking'] = booking
        elif ride:
            filter_kwargs['ride'] = ride
        else:
            filter_kwargs['cargo_ride'] = cargo_ride
            
        existing = Rating.objects.filter(**filter_kwargs).exists()
        
        if existing:
            return Response(
                {'error': 'You have already submitted a rating for this service'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            rating = Rating.objects.create(
                booking=booking,
                ride=ride,
                cargo_ride=cargo_ride,
                reviewer=request.user,
                reviewee=reviewee,
                category=category,
                overall_rating=serializer.validated_data['overall_rating'],
                reliability_rating=serializer.validated_data.get('reliability_rating'),
                communication_rating=serializer.validated_data.get('communication_rating'),
                cleanliness_rating=serializer.validated_data.get('cleanliness_rating'),
                timeliness_rating=serializer.validated_data.get('timeliness_rating'),
                title=serializer.validated_data.get('title', ''),
                comment=serializer.validated_data.get('comment', ''),
                private_feedback=serializer.validated_data.get('private_feedback', ''),
                asset_rating=serializer.validated_data.get('asset_rating'),
                status=RatingStatus.APPROVED
            )
            
            # Update user's trust score (handling 1-5 scale)
            reviewee.update_trust_score(rating.overall_rating)
        
        response_serializer = RatingSerializer(rating)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reveal(self, request, pk=None):
        """Reveal rating to the other party (after both have submitted)."""
        rating = self.get_object()
        
        if rating.reviewer != request.user:
            return Response(
                {'error': 'Only the reviewer can reveal their rating'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Check if there's a matching rating from the other party
        matching_rating = Rating.objects.filter(
            booking=rating.booking,
            ride=rating.ride,
            cargo_ride=rating.cargo_ride,
            reviewer=rating.reviewee,
            reviewee=rating.reviewer
        ).first()
        
        if not matching_rating:
            return Response(
                {'error': 'Cannot reveal - other party has not rated yet'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reveal both ratings
        rating.reveal_mutually()
        matching_rating.reveal_mutually()
        
        serializer = RatingSerializer(rating)
        return Response(serializer.data)

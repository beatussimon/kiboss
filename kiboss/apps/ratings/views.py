"""
Views for Ratings API
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from kiboss.apps.ratings.models import Rating, TrustDetails, RatingCategory, RatingStatus
from kiboss.apps.ratings.serializers import (
    RatingSerializer, RatingCreateSerializer, TrustDetailsSerializer
)
from kiboss.apps.bookings.models import Booking, BookingStatus


class RatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ratings.
    """
    queryset = Rating.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RatingCreateSerializer
        return RatingSerializer
    
    def get_queryset(self):
        queryset = Rating.objects.select_related(
            'booking', 'booking__asset', 'reviewer', 'reviewee'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by user (as reviewer or reviewee)
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(reviewer_id=user_id) | queryset.filter(reviewee_id=user_id)
        
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
        
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                return Response(
                    {'error': 'Booking not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Check if booking is completed (ratings only allowed after completion)
        if booking and booking.status != BookingStatus.COMPLETED:
            return Response(
                {'error': 'Can only rate after booking is completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine reviewee based on category
        category = serializer.validated_data['category']
        
        if category == RatingCategory.RENTER_TO_OWNER:
            if not booking:
                return Response(
                    {'error': 'booking_id required for RENTER_TO_OWNER rating'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            reviewee = booking.asset.owner
        elif category == RatingCategory.OWNER_TO_RENTER:
            if not booking:
                return Response(
                    {'error': 'booking_id required for OWNER_TO_RENTER rating'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            reviewee = booking.renter
        else:
            reviewee = None
        
        # Check if user already rated this booking
        existing = Rating.objects.filter(
            booking=booking,
            reviewer=request.user
        ).exists()
        
        if existing:
            return Response(
                {'error': 'You have already rated this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            rating = Rating.objects.create(
                booking=booking,
                ride_id=ride_id,
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
                status=RatingStatus.SUBMITTED
            )
            
            # Update user's trust score
            reviewee.update_trust_score(rating.overall_rating)
        
        response_serializer = RatingSerializer(rating)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def reveal(self, request, pk=None):
        """Reveal rating to the other party (after both have submitted)."""
        rating = self.get_object()
        
        # Check if there's a matching rating from the other party
        matching_rating = Rating.objects.filter(
            booking=rating.booking,
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


class TrustDetailsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing trust details.
    """
    queryset = TrustDetails.objects.all()
    serializer_class = TrustDetailsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = TrustDetails.objects.select_related('user')
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset

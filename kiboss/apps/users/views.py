"""
Views for Users API
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import User, UserProfile
from .serializers import UserWithProfileSerializer, UserProfileSerializer, PublicUserSerializer


class CurrentUserView(APIView):
    """
    API endpoint for getting and updating the current authenticated user.
    
    GET /api/v1/users/me/
    PATCH /api/v1/users/me/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """Get current user profile."""
        user = request.user
        serializer = UserWithProfileSerializer(user)
        return Response(serializer.data)
    
    def patch(self, request):
        """Update current user profile."""
        user = request.user
        
        # Separate user data from profile data
        user_data = {}
        profile_data = {}
        
        for key, value in request.data.items():
            if key in ['first_name', 'last_name']:
                user_data[key] = value
            elif key in ['phone', 'bio', 'avatar', 'address', 'city', 'state', 'country', 'postal_code']:
                profile_data[key] = value
        
        # Update user fields
        if user_data:
            user_serializer = UserWithProfileSerializer(user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
            else:
                return Response(
                    {'error': 'Failed to update user', 'details': user_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update or create profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        if profile_data:
            profile_serializer = UserProfileSerializer(profile, data=profile_data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                return Response(
                    {'error': 'Failed to update profile', 'details': profile_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Return updated user with profile
        serializer = UserWithProfileSerializer(user)
        return Response(serializer.data)


class PublicUserView(APIView):
    """
    API endpoint for getting public user profiles.
    
    GET /api/v1/users/{user_id}/public/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        """Get public user profile."""
        try:
            user = User.objects.select_related('profile').get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PublicUserSerializer(user, context={'request': request})
        return Response(serializer.data)


class RegisterView(APIView):
    """
    API endpoint for registering users.

    POST /api/v1/users/register/
    """
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        password_confirm = request.data.get('password_confirm')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        if not email or not password:
            return Response(
                {'error': 'email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if password_confirm is not None and password != password_confirm:
            return Response(
                {'error': 'Passwords do not match'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'A user with this email already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        # Create profile and trust score
        UserProfile.objects.get_or_create(user=user)
        from .models import TrustScore
        TrustScore.objects.get_or_create(user=user)
        
        serializer = UserWithProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

"""
Custom serializers for Users app
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserProfile


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count', 'is_blocked',
        ]
        read_only_fields = ['id', 'is_email_verified', 'is_phone_verified', 'is_identity_verified', 'trust_score', 'total_ratings_count', 'is_blocked']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that includes user data in response."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace username field with email field
        self.fields['email'] = serializers.EmailField()
        self.fields['password'] = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate credentials and return tokens."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError({
                'non_field_errors': ['Must include "email" and "password".']
            })
        
        # Authenticate using email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'non_field_errors': ['No active account found with the given credentials']
            })
        
        if not user.check_password(password):
            raise serializers.ValidationError({
                'non_field_errors': ['No active account found with the given credentials']
            })
        
        if not user.is_active:
            raise serializers.ValidationError({
                'non_field_errors': ['User account is disabled']
            })
        
        if user.is_blocked:
            raise serializers.ValidationError({
                'non_field_errors': ['User account has been blocked']
            })
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Note: last login is updated by SIMPLE_JWT's UPDATE_LAST_LOGIN setting
        
        # Prepare response data
        data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }
        
        return data
    
    @classmethod
    def get_token(cls, user):
        """Add custom claims to token."""
        token = super().get_token(user)
        # Add custom claims to token
        token['email'] = user.email
        token['user_id'] = str(user.id)
        return token

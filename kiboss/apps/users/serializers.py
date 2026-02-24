"""
Custom serializers for Users app
"""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserProfile, CorporateProfile


class CorporateProfileSerializer(serializers.ModelSerializer):
    """Serializer for CorporateProfile model."""
    class Meta:
        model = CorporateProfile
        fields = ['id', 'company_name', 'registration_number', 'tax_id', 'verification_status', 'business_category', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'phone', 'avatar', 'bio', 'date_of_birth',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'timezone', 'language', 'currency',
            'notification_settings',
            'total_bookings', 'total_listings',
            'total_rides_as_driver', 'total_rides_as_passenger',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_bookings', 'total_listings', 'total_rides_as_driver', 'total_rides_as_passenger', 'created_at', 'updated_at']


class UserWithProfileSerializer(serializers.ModelSerializer):
    """Serializer for User model with profile data."""
    profile = UserProfileSerializer(read_only=True)
    corporate_profile = CorporateProfileSerializer(read_only=True)
    verification_badge = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count', 'is_blocked',
            'verification_tier', 'verification_badge',
            'is_staff', 'is_superuser',
            'profile', 'corporate_profile', 'roles', 'permissions',
        ]
        read_only_fields = [
            'id', 'is_email_verified', 'is_phone_verified', 'is_identity_verified', 
            'trust_score', 'total_ratings_count', 'is_blocked', 
            'verification_badge', 'roles', 'permissions', 'is_staff', 'is_superuser',
            'corporate_profile'
        ]
    
    def get_verification_badge(self, obj):
        """Get verification badge info."""
        return obj.verification_badge

    def get_roles(self, obj):
        """Get user roles."""
        from kiboss.apps.rbac.serializers import UserRoleSerializer
        return UserRoleSerializer(obj.user_roles.all(), many=True).data

    def get_permissions(self, obj):
        """Get flattened list of unique permission codes."""
        from kiboss.apps.rbac.models import RolePermission
        roles = obj.user_roles.values_list('role', flat=True)
        perms = RolePermission.objects.filter(role__in=roles).values_list('permission', flat=True)
        return list(set(perms))


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    profile = UserProfileSerializer(read_only=True)
    corporate_profile = CorporateProfileSerializer(read_only=True)
    verification_badge = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count', 'is_blocked',
            'verification_tier', 'verification_badge',
            'is_staff', 'is_superuser',
            'roles', 'permissions', 'profile', 'corporate_profile',
        ]
        read_only_fields = [
            'id', 'is_email_verified', 'is_phone_verified', 'is_identity_verified', 
            'trust_score', 'total_ratings_count', 'is_blocked', 
            'verification_badge', 'roles', 'permissions', 'is_staff', 'is_superuser', 
            'profile', 'corporate_profile'
        ]
    
    def get_verification_badge(self, obj):
        """Get verification badge info."""
        return obj.verification_badge

    def get_roles(self, obj):
        """Get user roles."""
        from kiboss.apps.rbac.serializers import UserRoleSerializer
        return UserRoleSerializer(obj.user_roles.all(), many=True).data

    def get_permissions(self, obj):
        """Get flattened list of unique permission codes."""
        from kiboss.apps.rbac.models import RolePermission
        roles = obj.user_roles.values_list('role', flat=True)
        perms = RolePermission.objects.filter(role__in=roles).values_list('permission', flat=True)
        return list(set(perms))


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
            raise AuthenticationFailed('Must include "email" and "password".')
        
        # Authenticate using email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed('No active account found with the given credentials')

        if not user.check_password(password):
            raise AuthenticationFailed('No active account found with the given credentials')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        if user.is_blocked:
            raise AuthenticationFailed('User account has been blocked')
        
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


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user profile (used for viewing other users)."""
    verification_badge = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count',
            'verification_tier', 'verification_badge',
        ]
    
    def get_verification_badge(self, obj):
        """Get verification badge info."""
        return obj.verification_badge
    
    def to_representation(self, instance):
        """Add profile data to the response."""
        data = super().to_representation(instance)
        # Add profile data if available
        if hasattr(instance, 'profile') and instance.profile:
            data['avatar'] = instance.profile.avatar.url if instance.profile.avatar else None
            data['bio'] = instance.profile.bio or ''
            data['location'] = f"{instance.profile.city or ''}, {instance.profile.country or ''}".strip() or 'Location not set'
        else:
            data['avatar'] = None
            data['bio'] = ''
            data['location'] = 'Location not set'
        
        # Add date joined
        data['date_joined'] = instance.date_joined.isoformat() if instance.date_joined else None
        
        # Add empty arrays for listings, rides, reviews (these would need separate API calls)
        data['listings'] = []
        data['rides'] = []
        data['reviews'] = []
        data['rating'] = float(instance.trust_score) / 20 if instance.trust_score else 0
        data['review_count'] = instance.total_ratings_count
        
        # Check if following
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from kiboss.apps.social.models import Follow
            data['is_following'] = Follow.objects.filter(
                follower=request.user,
                following=instance
            ).exists()
        else:
            data['is_following'] = False
            
        data['username'] = instance.email.split('@')[0] if instance.email else ''
        
        return data

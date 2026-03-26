"""
Custom serializers for Users app
"""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserProfile, CorporateProfile, CorporateWorker


class CorporateProfileSerializer(serializers.ModelSerializer):
    """Serializer for CorporateProfile model."""
    class Meta:
        model = CorporateProfile
        fields = ['id', 'company_name', 'registration_number', 'tax_id', 'verification_status', 'business_category', 'created_at']


class CorporateWorkerSerializer(serializers.ModelSerializer):
    """Serializer for CorporateWorker model."""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = CorporateWorker
        fields = [
            'id', 'email', 'name', 'role', 'role_display',
            'status', 'status_display', 'user', 'user_name',
            'invited_at', 'accepted_at', 'deactivated_at',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'user_name', 'invited_at', 'accepted_at', 'deactivated_at', 'created_at']

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.name or obj.email


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'phone', 'avatar', 'avatar_url', 'bio', 'date_of_birth',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude',
            'timezone', 'language', 'currency',
            'notification_settings',
            'total_bookings', 'total_listings',
            'total_rides_as_driver', 'total_rides_as_passenger',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_bookings', 'total_listings', 'total_rides_as_driver', 'total_rides_as_passenger', 'created_at', 'updated_at']

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            if request is not None:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserWithProfileSerializer(serializers.ModelSerializer):
    """Serializer for User model with profile data."""
    profile = UserProfileSerializer(read_only=True)
    corporate_profile = CorporateProfileSerializer(read_only=True)
    verification_badge = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    total_listings = serializers.SerializerMethodField()
    total_rides = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count', 'is_blocked',
            'account_tier', 'verification_tier', 'verification_badge',
            'is_staff', 'is_superuser',
            'profile', 'corporate_profile', 'roles', 'permissions',
            'followers_count', 'following_count', 'total_listings', 'total_rides', 'total_reviews'
        ]
        read_only_fields = [
            'id', 'is_email_verified', 'is_phone_verified', 'is_identity_verified', 
            'trust_score', 'total_ratings_count', 'is_blocked', 
            'account_tier', 'verification_badge', 'roles', 'permissions', 'is_staff', 'is_superuser',
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
        
    def get_followers_count(self, obj):
        from kiboss.apps.social.models import Follow
        return Follow.objects.filter(following=obj).count()

    def get_following_count(self, obj):
        from kiboss.apps.social.models import Follow
        return Follow.objects.filter(follower=obj).count()

    def get_total_listings(self, obj):
        from kiboss.apps.assets.models import Asset
        return Asset.objects.filter(owner=obj, is_active=True).count()

    def get_total_rides(self, obj):
        from kiboss.apps.rides.models import Ride
        return Ride.objects.filter(driver=obj).count()

    def get_total_reviews(self, obj):
        from kiboss.apps.ratings.models import Rating
        return Rating.objects.filter(reviewee=obj, status='APPROVED').count()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    profile = UserProfileSerializer(read_only=True)
    corporate_profile = CorporateProfileSerializer(read_only=True)
    verification_badge = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    total_listings = serializers.SerializerMethodField()
    total_rides = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'is_email_verified', 'is_phone_verified', 'is_identity_verified',
            'trust_score', 'total_ratings_count', 'is_blocked',
            'account_tier', 'verification_tier', 'verification_badge',
            'is_staff', 'is_superuser',
            'profile', 'corporate_profile', 'roles', 'permissions',
            'followers_count', 'following_count', 'total_listings', 'total_rides', 'total_reviews'
        ]
        read_only_fields = [
            'id', 'is_email_verified', 'is_phone_verified', 'is_identity_verified', 
            'trust_score', 'total_ratings_count', 'is_blocked', 
            'account_tier', 'verification_badge', 'roles', 'permissions', 'is_staff', 'is_superuser', 
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

    def get_followers_count(self, obj):
        from kiboss.apps.social.models import Follow
        return Follow.objects.filter(following=obj).count()

    def get_following_count(self, obj):
        from kiboss.apps.social.models import Follow
        return Follow.objects.filter(follower=obj).count()

    def get_total_listings(self, obj):
        from kiboss.apps.assets.models import Asset
        return Asset.objects.filter(owner=obj, is_active=True).count()

    def get_total_rides(self, obj):
        from kiboss.apps.rides.models import Ride
        return Ride.objects.filter(driver=obj).count()

    def get_total_reviews(self, obj):
        from kiboss.apps.ratings.models import Rating
        return Rating.objects.filter(reviewee=obj, status='APPROVED').count()


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
        request = self.context.get('request')
        if hasattr(instance, 'profile') and instance.profile:
            if instance.profile.avatar and hasattr(instance.profile.avatar, 'url'):
                data['avatar'] = request.build_absolute_uri(instance.profile.avatar.url) if request else instance.profile.avatar.url
            else:
                data['avatar'] = None
            data['bio'] = instance.profile.bio or ''
            data['location'] = f"{instance.profile.city or ''}, {instance.profile.country or ''}".strip() or 'Location not set'
        else:
            data['avatar'] = None
            data['bio'] = ''
            data['location'] = 'Location not set'
        
        # Add date joined
        data['date_joined'] = instance.date_joined.isoformat() if instance.date_joined else None
        
        # Add dynamic counts and arrays
        from kiboss.apps.social.models import Follow
        from kiboss.apps.assets.models import Asset
        from kiboss.apps.rides.models import Ride
        from kiboss.apps.ratings.models import Rating
        
        data['follower_count'] = Follow.objects.filter(following=instance).count()
        data['following_count'] = Follow.objects.filter(follower=instance).count()
        
        # Listings
        assets = Asset.objects.filter(owner=instance, is_active=True)[:10]
        data['listings'] = []
        for asset in assets:
            price = 0
            price_rule = asset.pricing_rules.filter(is_active=True).first()
            if price_rule:
                price = price_rule.price
                
            # Get primary photo URL
            primary_photo = asset.photos.filter(is_primary=True).first() or asset.photos.first()
            photo_url = request.build_absolute_uri(primary_photo.image.url) if primary_photo and request else (primary_photo.image.url if primary_photo else None)
            
            data['listings'].append({
                'id': asset.id,
                'title': asset.name,
                'type': asset.get_asset_type_display(),
                'price': price,
                'photo_url': photo_url
            })
            
        # Rides
        rides = Ride.objects.filter(driver=instance, status='SCHEDULED')[:10]
        data['rides'] = []
        for ride in rides:
            data['rides'].append({
                'id': str(ride.id),
                'origin': ride.origin if ride.origin else 'Unknown',
                'destination': ride.destination if ride.destination else 'Unknown',
                'departure_time': ride.departure_time.isoformat() if ride.departure_time else None,
                'price': str(ride.seat_price) if ride.seat_price else '0'
            })
            
        # Reviews
        reviews = Rating.objects.filter(reviewee=instance, status='APPROVED')[:10]
        data['reviews'] = []
        for review in reviews:
            data['reviews'].append({
                'id': str(review.id),
                'rating': review.overall_rating,
                'comment': review.comment,
                'reviewer': {
                    'first_name': review.reviewer.first_name if review.reviewer else 'Anonymous'
                }
            })
            
        data['rating'] = float(instance.trust_score) / 20 if hasattr(instance, 'trust_score') and instance.trust_score else 0
        data['review_count'] = getattr(instance, 'total_ratings_count', 0)
        
        data['total_listings'] = Asset.objects.filter(owner=instance, is_active=True).count()
        data['total_rides'] = Ride.objects.filter(driver=instance).count()
        data['total_reviews'] = data['review_count']
        
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

"""
Views for Users API
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import User, UserProfile, CorporateProfile, BusinessSubscription
from .serializers import UserWithProfileSerializer, UserProfileSerializer, PublicUserSerializer, UserSerializer
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
from kiboss.apps.core.models import SystemConfiguration
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta


class BusinessConfigView(APIView):
    """
    Fetch global business settings (pricing, terms).
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        config = SystemConfiguration.get_config()
        return Response({
            'monthly_price': float(config.business_subscription_monthly),
            'yearly_price': float(config.business_subscription_yearly),
            'registration_fee': float(config.business_registration_fee),
            'terms': config.business_terms_conditions
        })


class CorporateRegistrationView(APIView):
    """
    API endpoint for corporate account registration.
    Supports plan selection, payment reference, and document uploads.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        user = request.user
        
        # Check if already registered
        if hasattr(user, 'corporate_profile'):
            return Response(
                {'error': 'Corporate profile already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        company_name = request.data.get('company_name')
        registration_number = request.data.get('registration_number')
        country = request.data.get('country', 'Tanzania')
        plan_type = request.data.get('plan_type', 'MONTHLY') # 'MONTHLY' or 'YEARLY'
        payment_reference = request.data.get('payment_reference', '')
        
        if not company_name or not registration_number:
            return Response(
                {'error': 'Company name and registration number are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle file uploads
        files = request.FILES.getlist('documents')
        uploaded_docs = []
        for file in files:
            # In a real app, we'd save to a proper storage and keep the URL
            # For now, we'll use the file name as a placeholder in the JSONField
            # but ideally these should be saved to a FileField or dedicated model
            uploaded_docs.append({
                'name': file.name,
                'size': file.size,
                'type': file.content_type,
                'uploaded_at': timezone.now().isoformat()
            })

        with transaction.atomic():
            # Create profile
            profile = CorporateProfile.objects.create(
                user=user,
                company_name=company_name,
                registration_number=registration_number,
                tax_id=request.data.get('tax_id', ''),
                verification_status='PENDING',
                verification_documents=uploaded_docs
            )
            
            # Save country to user profile if it's there
            user_profile, _ = UserProfile.objects.get_or_create(user=user)
            user_profile.country = country
            user_profile.save()
            
            # Create Subscription record
            config = SystemConfiguration.get_config()
            price = config.business_subscription_monthly if plan_type == 'MONTHLY' else config.business_subscription_yearly
            duration_days = 30 if plan_type == 'MONTHLY' else 365
            
            BusinessSubscription.objects.create(
                profile=profile,
                plan_type=plan_type,
                status='PENDING',
                amount_paid=price,
                end_date=timezone.now() + timedelta(days=duration_days),
                payment_reference=payment_reference
            )
            
            # Create Verification Task using service
            from kiboss.apps.common.services import VerificationService
            VerificationService.request_verification(profile, user, notes=f"Plan: {plan_type}. Ref: {payment_reference}")
        
        return Response({
            'status': 'success',
            'message': 'Corporate application and subscription submitted successfully',
            'profile_id': str(profile.id)
        }, status=status.HTTP_201_CREATED)


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
        
        # Merge POST data and FILES
        # request.data already includes both for MultiPartParser
        for key, value in request.data.items():
            if key in ['first_name', 'last_name']:
                user_data[key] = value
            elif key in ['phone', 'bio', 'avatar', 'address', 'city', 'state', 'country', 'postal_code']:
                profile_data[key] = value
        
        # Explicitly check request.FILES for avatar if not found in request.data
        if 'avatar' in request.FILES:
            profile_data['avatar'] = request.FILES['avatar']
        
        print(f"DEBUG: Updating user {user.email}. user_data keys: {list(user_data.keys())}, profile_data keys: {list(profile_data.keys())}")
        
        # Update user fields
        if user_data:
            user_serializer = UserSerializer(user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
            else:
                print(f"DEBUG: User update failed: {user_serializer.errors}")
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
                print(f"DEBUG: Profile update failed: {profile_serializer.errors}")
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
    permission_classes = [AllowAny]

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
        
        # Trigger email verification
        from kiboss.apps.users.verification_models import VerificationRequest, VerificationType
        verification = VerificationRequest.objects.create(
            user=user,
            verification_type=VerificationType.EMAIL,
            email=user.email
        )
        verification.generate_code()
        # TODO: A Celery task would dispatch the email here
        
        serializer = UserWithProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """
    API endpoint for verifying user's email address using a six digit code.
    
    POST /api/v1/users/verify-email/
    """
    from rest_framework.permissions import IsAuthenticated
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Verification code is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from kiboss.apps.users.verification_models import VerificationRequest, VerificationType, VerificationStatus
        verification = VerificationRequest.objects.filter(
            user=request.user,
            verification_type=VerificationType.EMAIL,
            status=VerificationStatus.PENDING
        ).last()

        if not verification:
            return Response({'error': 'No pending email verification found'}, status=status.HTTP_404_NOT_FOUND)
        
        success, message = verification.verify_code(code)
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

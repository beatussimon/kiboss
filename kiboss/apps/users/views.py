"""
Views for Users API
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import User, UserProfile, CorporateProfile, BusinessSubscription, CorporateWorker
from .serializers import UserWithProfileSerializer, UserProfileSerializer, PublicUserSerializer, UserSerializer, CorporateWorkerSerializer
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
from kiboss.apps.core.models import SystemConfiguration
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
from django.db import transaction


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
        
        # Check Staff Isolation
        if user.is_staff:
            return Response(
                {'error': 'Staff members cannot create Corporate Profiles.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
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
        business_category = request.data.get('business_category', 'ASSET')
        
        if not company_name or not registration_number:
            return Response(
                {'error': 'Company name and registration number are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle file uploads
        files = request.FILES.getlist('documents')
        uploaded_docs = []
        
        from django.core.files.storage import default_storage
        import os
        import uuid
        from kiboss.apps.common.validators import validate_file_size, validate_document_extension
        
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        for file in files:
            # Validate
            try:
                validate_file_size(file)
                validate_document_extension(file)
            except DjangoValidationError as e:
                return Response({'error': e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
            
            # Save physical file to storage
            ext = os.path.splitext(file.name)[1]
            filename = f"corporate_docs/{user.id}_{uuid.uuid4().hex}{ext}"
            saved_path = default_storage.save(filename, file)
            file_url = default_storage.url(saved_path)
            
            uploaded_docs.append({
                'name': file.name,
                'size': file.size,
                'type': file.content_type,
                'path': saved_path,
                'url': file_url,
                'uploaded_at': timezone.now().isoformat()
            })

        with transaction.atomic():
            # Create profile
            profile = CorporateProfile.objects.create(
                user=user,
                company_name=company_name,
                registration_number=registration_number,
                tax_id=request.data.get('tax_id', ''),
                business_category=business_category,
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

    def patch(self, request):
        user = request.user
        
        try:
            profile = user.corporate_profile
        except CorporateProfile.DoesNotExist:
            return Response(
                {'error': 'No existing corporate profile found for this user.'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        company_name = request.data.get('company_name')
        registration_number = request.data.get('registration_number')
        tax_id = request.data.get('tax_id')
        business_category = request.data.get('business_category')
        
        if company_name: profile.company_name = company_name
        if registration_number: profile.registration_number = registration_number
        if tax_id is not None: profile.tax_id = tax_id
        if business_category: profile.business_category = business_category
        
        # Handle file uploads if new documents are provided
        files = request.FILES.getlist('documents')
        if files:
            from django.core.files.storage import default_storage
            import os
            import uuid
            from kiboss.apps.common.validators import validate_file_size, validate_document_extension
            
            existing_docs = profile.verification_documents or []
            
            for file in files:
                validate_file_size(file)
                validate_document_extension(file)
                
                ext = os.path.splitext(file.name)[1]
                filename = f"corporate_docs/{user.id}_{uuid.uuid4().hex}{ext}"
                saved_path = default_storage.save(filename, file)
                file_url = default_storage.url(saved_path)
                
                existing_docs.append({
                    'name': file.name,
                    'size': file.size,
                    'type': file.content_type,
                    'path': saved_path,
                    'url': file_url,
                    'uploaded_at': timezone.now().isoformat()
                })
            
            profile.verification_documents = existing_docs
            
        with transaction.atomic():
            # Reset verification status
            profile.verification_status = 'PENDING'
            profile.save()
            
            # Update subscription if a new payment reference was provided
            payment_reference = request.data.get('payment_reference')
            plan_type = request.data.get('plan_type')
            notes = "Resubmission."
            
            if payment_reference and plan_type:
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
                notes = f"Plan: {plan_type}. Ref: {payment_reference}"
                
            # Create a new verification task
            from kiboss.apps.common.services import VerificationService
            VerificationService.request_verification(profile, user, notes=notes)
            
        return Response({
            'status': 'success',
            'message': 'Corporate profile updated and resubmitted for verification',
            'profile_id': str(profile.id)
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        user = request.user
        
        try:
            profile = user.corporate_profile
        except CorporateProfile.DoesNotExist:
            return Response(
                {'error': 'No existing corporate profile found for this user.'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        with transaction.atomic():
            # Delete any verification tasks for this profile created by this user
            try:
                from django.contrib.contenttypes.models import ContentType
                from kiboss.apps.tasks.models import StaffTask
                content_type = ContentType.objects.get_for_model(profile)
                StaffTask.objects.filter(content_type=content_type, object_id=profile.id).delete()
            except Exception as e:
                print(f"Failed to delete associated verification tasks: {e}")
                
            # Delete profile (which cascades to subscriptions)
            profile.delete()
            
        return Response({
            'status': 'success',
            'message': 'Corporate application cancelled successfully'
        }, status=status.HTTP_204_NO_CONTENT)


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
            return Response({'error': 'Invalid or expired verification code.'}, status=status.HTTP_400_BAD_REQUEST)
        
        success, message = verification.verify_code(code)
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)


class CorporateWorkerViewSet(APIView):
    """
    API endpoint for managing corporate workers.
    GET: List all workers for the current corporate profile.
    POST: Invite a new worker.
    PATCH: Update a worker (role or status).
    DELETE: Deactivate a worker.
    """
    permission_classes = [IsAuthenticated]

    def _get_corporate_profile(self, user):
        """Get verified corporate profile or raise error."""
        if not hasattr(user, 'corporate_profile'):
            return None
        cp = user.corporate_profile
        if cp.verification_status != 'VERIFIED':
            return None
        return cp

    def get(self, request):
        """List workers for the current corporate profile."""
        cp = self._get_corporate_profile(request.user)
        if not cp:
            return Response({'error': 'Verified corporate profile required.'}, status=status.HTTP_403_FORBIDDEN)
        
        workers = CorporateWorker.objects.filter(corporate_profile=cp).select_related('user').order_by('-created_at')
        serializer = CorporateWorkerSerializer(workers, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Invite a new worker."""
        cp = self._get_corporate_profile(request.user)
        if not cp:
            return Response({'error': 'Verified corporate profile required.'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CorporateWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Check if worker already exists
        if CorporateWorker.objects.filter(corporate_profile=cp, email=email).exists():
            return Response({'error': 'Worker with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Auto-link if user with this email exists in the system
        linked_user = User.objects.filter(email=email).first()
        worker_status = CorporateWorker.InviteStatus.ACTIVE if linked_user else CorporateWorker.InviteStatus.INVITED
        
        worker = serializer.save(
            corporate_profile=cp,
            user=linked_user,
            status=worker_status,
            accepted_at=timezone.now() if linked_user else None
        )
        
        return Response(CorporateWorkerSerializer(worker).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        """Update a worker's role or status."""
        cp = self._get_corporate_profile(request.user)
        if not cp:
            return Response({'error': 'Verified corporate profile required.'}, status=status.HTTP_403_FORBIDDEN)
        
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({'error': 'worker_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            worker = CorporateWorker.objects.get(id=worker_id, corporate_profile=cp)
        except CorporateWorker.DoesNotExist:
            return Response({'error': 'Worker not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Update role if provided
        new_role = request.data.get('role')
        if new_role and new_role in [r[0] for r in CorporateWorker.Role.choices]:
            worker.role = new_role
        
        # Update status if provided
        new_status = request.data.get('status')
        if new_status == 'DEACTIVATED':
            worker.status = CorporateWorker.InviteStatus.DEACTIVATED
            worker.deactivated_at = timezone.now()
        elif new_status == 'ACTIVE':
            worker.status = CorporateWorker.InviteStatus.ACTIVE
            worker.deactivated_at = None
        
        worker.save()
        return Response(CorporateWorkerSerializer(worker).data)

    def delete(self, request):
        """Remove a worker entirely."""
        cp = self._get_corporate_profile(request.user)
        if not cp:
            return Response({'error': 'Verified corporate profile required.'}, status=status.HTTP_403_FORBIDDEN)
        
        worker_id = request.query_params.get('worker_id')
        if not worker_id:
            return Response({'error': 'worker_id query param is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            worker = CorporateWorker.objects.get(id=worker_id, corporate_profile=cp)
        except CorporateWorker.DoesNotExist:
            return Response({'error': 'Worker not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        worker.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TierListView(APIView):
    """GET /api/v1/users/tiers/ - List all available tiers with features."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from kiboss.apps.users.tier_service import get_all_tiers
        tiers = get_all_tiers()
        return Response(tiers)


class UpgradeView(APIView):
    """POST /api/v1/users/upgrade/ - Upgrade user's account tier."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from kiboss.apps.users.tier_service import get_tier_features
        
        tier = request.data.get('tier')
        if tier not in ('PLUS', 'BUSINESS'):
            return Response(
                {'error': 'Invalid tier. Must be PLUS or BUSINESS'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        
        # Check current tier
        tier_order = {'FREE': 0, 'PLUS': 1, 'BUSINESS': 2}
        current_level = tier_order.get(user.account_tier, 0)
        target_level = tier_order.get(tier, 0)
        
        if target_level <= current_level:
            return Response(
                {'error': f'Cannot downgrade or stay at current tier ({user.account_tier})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For BUSINESS tier, require corporate profile
        if tier == 'BUSINESS':
            if not hasattr(user, 'corporate_profile'):
                return Response(
                    {'error': 'Business tier requires a corporate profile. Register your business first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Upgrade the tier (payment will be handled by ZenoPay integration)
        user.account_tier = tier
        user.save(update_fields=['account_tier', 'updated_at'])
        
        features = get_tier_features(tier)
        serializer = UserWithProfileSerializer(user)
        
        return Response({
            'message': f'Successfully upgraded to {tier} tier',
            'tier': tier,
            'features': features,
            'user': serializer.data
        })

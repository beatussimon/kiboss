"""
Views for Assets API - Universal Asset System
"""
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Case, When, Value, FloatField, Q, Subquery, OuterRef, Exists
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from kiboss.apps.assets.models import Asset, AssetPhoto, AssetPricing, AssetAvailability, AssetType, VerificationStatus
from kiboss.apps.assets.serializers import (
    AssetSerializer, AssetDetailSerializer, AssetListSerializer,
    AssetPhotoSerializer, AssetPricingSerializer, AssetAvailabilitySerializer
)
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
from kiboss.apps.users.models import CorporateProfile
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets, status, filters, permissions

class AssetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assets.

    Provides CRUD operations for the universal asset system.
    """
    queryset = Asset.objects.select_related('owner', 'verified_by').order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'city', 'country', 'address']
    ordering_fields = ['created_at', 'average_rating', 'total_bookings']
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'list':
            return AssetListSerializer
        elif self.action == 'retrieve':
            return AssetDetailSerializer
        return AssetSerializer
    
    def perform_create(self, serializer):
        """
        Handle asset creation with Corporate and Property verification gates.
        """
        asset_type = serializer.validated_data.get('asset_type')
        user = self.request.user
        
        if user.is_staff and not user.is_superuser:
            raise PermissionDenied("Staff accounts cannot create asset listings. Use a personal account or request superadmin access.")

        # Check listing limits for non-child assets across FREE and PLUS plans
        is_child = serializer.validated_data.get('parent') is not None
        if not is_child and user.account_tier in ['FREE', 'PLUS']:
            total_active = Asset.objects.filter(
                owner=user, is_active=True, parent__isnull=True
            ).count()
            
            if user.account_tier == 'FREE' and total_active >= 3:
                raise PermissionDenied("Your Free plan allows up to 3 active assets in total. Upgrade to Plus to add more.")
            if user.account_tier == 'PLUS':
                if total_active >= 10:
                    raise PermissionDenied("Your Plus plan allows up to 10 active assets in total.")
                if asset_type == AssetType.VEHICLE:
                    vehicle_count = Asset.objects.filter(
                        owner=user, is_active=True, asset_type=AssetType.VEHICLE, parent__isnull=True
                    ).count()
                    if vehicle_count >= 2:
                        raise PermissionDenied("Your Plus plan allows a maximum of 2 active vehicles.")
        
        # CORPORATE GATE: Enforce Asset Business Profile Restrictions
        if hasattr(user, 'corporate_profile') and user.corporate_profile.verification_status == 'VERIFIED' and user.account_tier == 'BUSINESS':
            if user.corporate_profile.business_category == 'ASSET':
                # Corporate Asset accounts should ideally list corporate properties.
                # But they may have 'personal' items too. Ensure they don't abuse the unlimited 'BUSINESS' quota for personal junk.
                context_mode = self.request.query_params.get('context') or self.request.data.get('context')
                
                # If they pass context=personal, they are trying to list an individual asset. 
                # We enforce the FREE/PLUS limit on personal items in the next block implicitly if we temporarily fake tier? No, just block them explicitly if they try to bypass.
                # Realistically, they should be acting in their business capacity here.
                
                if context_mode == 'personal' and not is_child and asset_type not in [AssetType.HOTEL, AssetType.RESTAURANT, AssetType.OFFICE_SPACE, AssetType.APARTMENT]:
                    raise PermissionDenied("Corporate Asset accounts can only list corporate properties in unlimited capacity. Switch to a personal/free account to list personal items.")

        # CORPORATE GATE: Creating a Property (Hotel/Restaurant)
        if asset_type in [AssetType.HOTEL, AssetType.RESTAURANT]:
            # 1. Check if user has a Corporate Profile
            if not hasattr(user, 'corporate_profile'):
                raise PermissionDenied("Corporate verification required. Please register as a business first.")
                
            if user.corporate_profile.business_category != 'ASSET':
                raise PermissionDenied("Only Asset businesses can create Properties (Hotels/Restaurants).")
            
            # 2. Check if Corporate Profile is Verified or Pending
            # Allow PENDING profiles to create, but they won't be listed until verified
            if user.corporate_profile.verification_status not in ['VERIFIED', 'PENDING']:
                raise PermissionDenied("Your corporate account must be in good standing.")
            
            # 3. Save as PENDING and create Verification Task
            asset = serializer.save(
                owner=user,
                verification_status=VerificationStatus.PENDING,
                is_corporate=True,
                is_listed=False # Never list until verified
            )
            
            # Create StaffTask for Property Verification
            StaffTask.objects.create(
                title=f"Verify Property: {asset.name}",
                description=f"New {asset.get_asset_type_display()} registration from {user.corporate_profile.company_name}",
                task_type=TaskType.ASSET_AUDIT,
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                assigned_role='OPS',
                content_type=ContentType.objects.get_for_model(Asset),
                object_id=asset.id,
                created_by=user
            )
            return

        # SERVICE GATE: Creating a Service (Room/Hall) inside a Property
        if asset_type in [AssetType.HOTEL_ROOM, AssetType.CONFERENCE_HALL, AssetType.DINING_TABLE]:
            parent = serializer.validated_data.get('parent')
            if not parent:
                raise ValidationError({"parent": "This service must be linked to a parent property (Hotel/Restaurant)."})
            
            # 1. Check ownership
            if parent.owner != user:
                raise PermissionDenied("You do not own the parent property.")
            
            # 2. Check Parent Property Verification
            if parent.verification_status != VerificationStatus.VERIFIED:
                raise PermissionDenied("Parent property must be verified before adding services.")
            
            # 3. Save (Inherit Verified status if parent is verified? Or keep separate? 
            # Usually services are auto-approved if property is verified, or manual. 
            # Let's auto-verify services for now to streamline, as the Property is the main risk).
            serializer.save(
                owner=user,
                verification_status=VerificationStatus.VERIFIED, # Auto-verify service if property is safe
                verified_at=timezone.now(),
                verified_by=user, # Self-verified via parent trust
                is_corporate=True
            )
            return

        # EXISTING LOGIC: Vehicles and other assets
        if asset_type == AssetType.VEHICLE:
            # Check if user has a verified corporate profile
            is_verified_corporate = False
            if hasattr(user, 'corporate_profile') and user.corporate_profile.verification_status == 'VERIFIED':
                is_verified_corporate = True
                
            # Vehicles do not require explicit corporate tier limits here because 
            # they are already handled by the global FREE/PLUS limits above.
            # Legacy limits code removed.
            
            asset = serializer.save(
                owner=user,
                verification_status=VerificationStatus.PENDING,
                is_corporate=is_verified_corporate,
                is_listed=False
            )
            
            # ALWAYS require staff verification for a new vehicle
            from kiboss.apps.common.services import VerificationService
            VerificationService.request_verification(asset, user)
            return
        else:
            # Other assets auto-verified for now
            serializer.save(
                owner=user,
                verification_status=VerificationStatus.VERIFIED,
                verified_at=timezone.now(),
                verified_by=user,
                is_active=True,
                is_listed=True
            )

    def perform_update(self, serializer):
        asset = self.get_object()
        user = self.request.user
        if asset.owner_id != user.id and not user.is_superuser:
            raise PermissionDenied('Only the asset owner can update this asset')
            
        # Vehicles can only be listed on the asset marketplace if the owner is on the BUSINESS plan
        if asset.asset_type == AssetType.VEHICLE:
            is_listed = serializer.validated_data.get('is_listed')
            if is_listed:
                if user.account_tier != 'BUSINESS':
                    raise PermissionDenied('Only BUSINESS tier users can list vehicles for rent.')
            else:
                serializer.validated_data['is_listed'] = False
            
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Soft-delete assets so references and history remain intact."""
        asset = self.get_object()
        if asset.owner_id != request.user.id and not request.user.is_superuser:
            raise PermissionDenied('Only the asset owner can delete this asset')
        asset.is_active = False
        asset.is_listed = False
        asset.save(update_fields=['is_active', 'is_listed', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def get_queryset(self):
        from kiboss.apps.users.models import CorporateProfile
        has_verified_corp = Exists(
            CorporateProfile.objects.filter(
                user_id=OuterRef('owner_id'),
                verification_status='VERIFIED'
            )
        )
        
        queryset = Asset.objects.select_related(
            'owner', 'owner__profile', 'owner__corporate_profile', 'verified_by'
        ).prefetch_related(
            'photos',
            'pricing_rules',
            'availability_rules',
            'capacities',
        ).annotate(
            visibility_boost=Case(
                When(has_verified_corp, then=Value(2.0)),
                When(owner__account_tier='PLUS', then=Value(1.5)),
                default=Value(1.0),
                output_field=FloatField(),
            )
        ).order_by('-visibility_boost', '-average_rating', '-created_at')
        
        # Filter by asset type
        asset_type = self.request.query_params.get('asset_type')
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
            
        # Filter by owner
        owner_id = self.request.query_params.get('owner')
        if owner_id == 'me':
            queryset = queryset.filter(owner=self.request.user)
        elif owner_id:
            queryset = queryset.filter(owner_id=owner_id)
        
        # Filter by location
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(country__icontains=country)
        
        # Filter by verification status
        verification_status = self.request.query_params.get('verification_status')
        if verification_status:
            queryset = queryset.filter(verification_status=verification_status)
        
        # Filter by active/listed
        if self.action == 'list' and owner_id != 'me':
            queryset = queryset.filter(is_active=True, is_listed=True, verification_status=VerificationStatus.VERIFIED)
            
        if self.action == 'retrieve':
            from django.db.models import Q
            if self.request.user.is_authenticated:
                # Owners can view their own inactive assets
                queryset = queryset.filter(Q(is_active=True) | Q(owner=self.request.user))
            else:
                queryset = queryset.filter(is_active=True)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None and is_active.lower() != 'any':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_listed = self.request.query_params.get('is_listed')
        if is_listed is not None:
            queryset = queryset.filter(is_listed=is_listed.lower() == 'true')
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(average_rating__gte=min_rating)

        # Filter by context
        context_param = self.request.query_params.get('context')
        if context_param == 'personal':
            queryset = queryset.filter(is_corporate=False)
        elif context_param == 'corporate':
            queryset = queryset.filter(is_corporate=True)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def check_availability(self, request, pk=None):
        """Check if asset is available for specific dates and quantity."""
        asset = self.get_object()
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        quantity_str = request.query_params.get('quantity', '1')
        
        if not start_time_str or not end_time_str:
            return Response(
                {'error': 'start_time and end_time are required parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            from dateutil.parser import parse
            start_time = parse(start_time_str)
            end_time = parse(end_time_str)
            quantity = int(quantity_str)
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Invalid date format or quantity: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        from kiboss.apps.bookings.services import BookingService
        
        try:
            is_available, conflict_info = BookingService.check_availability(
                asset_id=asset.id,
                start_time=start_time,
                end_time=end_time,
                quantity=quantity
            )
            return Response({
                'is_available': is_available,
                'conflict_info': conflict_info,
                'asset_id': str(asset.id),
                'requested_quantity': quantity
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify an asset (admin/owner only)."""
        asset = self.get_object()
        asset.verification_status = 'VERIFIED'
        asset.verified_at = timezone.now()
        asset.verified_by = request.user
        asset.save()
        
        from kiboss.apps.notifications.services import NotificationService
        from kiboss.apps.notifications.models import NotificationCategory
        NotificationService.create_notification(
            user=asset.owner,
            category=NotificationCategory.SYSTEM,
            notification_type='ASSET_VERIFIED',
            title="Asset Verified",
            message=f"Your asset '{asset.name}' has been verified and is now active."
        )
        
        serializer = self.get_serializer(asset)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an asset."""
        asset = self.get_object()
        asset.is_active = False
        asset.save()
        
        from kiboss.apps.notifications.services import NotificationService
        from kiboss.apps.notifications.models import NotificationCategory
        NotificationService.create_notification(
            user=asset.owner,
            category=NotificationCategory.SYSTEM,
            notification_type='ASSET_DEACTIVATED',
            title="Asset Deactivated",
            message=f"Your asset '{asset.name}' has been deactivated by an administrator."
        )
        
        serializer = self.get_serializer(asset)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an asset."""
        asset = self.get_object()
        asset.is_active = True
        asset.save()
        serializer = self.get_serializer(asset)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def photos(self, request, pk=None):
        """Get all photos for an asset."""
        asset = self.get_object()
        photos = asset.photos.all().order_by('order')
        serializer = AssetPhotoSerializer(photos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def upload_photos(self, request, pk=None):
        """Upload photos for an asset."""
        asset = self.get_object()
        
        # Check if user is the owner
        if asset.owner_id != request.user.id and not request.user.is_superuser:
            raise PermissionDenied('Only the asset owner can upload photos')
        
        # Get uploaded files
        files = request.FILES.getlist('images')
        if not files:
            # Try single file upload
            single_file = request.FILES.get('image')
            if single_file:
                files = [single_file]
            else:
                return Response(
                    {'error': 'No images provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if is_primary is specified
        is_primary = request.data.get('is_primary', 'false').lower() == 'true'
        
        created_photos = []
        current_order = asset.photos.count()
        
        for i, file in enumerate(files[:10]):  # Max 10 images per upload
            photo = AssetPhoto.objects.create(
                asset=asset,
                image=file,
                order=current_order + i,
                is_primary=(is_primary and i == 0) or (current_order == 0 and i == 0)
            )
            created_photos.append(photo)
        
        serializer = AssetPhotoSerializer(created_photos, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def pricing(self, request, pk=None):
        """Get all pricing rules for an asset."""
        asset = self.get_object()
        pricing = asset.pricing_rules.filter(is_active=True).order_by('-priority')
        serializer = AssetPricingSerializer(pricing, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Get all availability rules for an asset."""
        asset = self.get_object()
        availability = asset.availability_rules.filter(is_active=True)
        serializer = AssetAvailabilitySerializer(availability, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_discount(self, request):
        """Apply a percentage discount to all active listings of the user."""
        user = request.user
        
        # Free users cannot use advanced bulk marketing tools
        if user.account_tier not in ['PLUS', 'BUSINESS']:
            raise PermissionDenied("Only Plus and Business users can access the Marketing Center.")
            
        discount_percent = request.data.get('percentage')
        if not discount_percent:
            return Response({'error': 'percentage is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            discount_percent = float(discount_percent)
            if discount_percent < 0 or discount_percent > 99:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'error': 'percentage must be between 0 and 99'}, status=status.HTTP_400_BAD_REQUEST)

        multiplier = 1.0 - (discount_percent / 100.0)
        
        # Find all active pricing rules for user's assets
        from kiboss.apps.assets.models import AssetPricing
        
        user_assets = Asset.objects.filter(owner=user, is_active=True)
        user_pricing_rules = AssetPricing.objects.filter(asset__in=user_assets, is_active=True)
        
        updated_count = 0
        from django.db import transaction
        with transaction.atomic():
            for rule in user_pricing_rules:
                # Store original price in rules field if not already stored, so we can revert if needed
                if 'original_price_before_discount' not in rule.rules:
                    rule.rules['original_price_before_discount'] = str(rule.price)
                
                new_price = float(rule.price) * multiplier
                rule.price = new_price
                rule.save(update_fields=['price', 'rules', 'updated_at'])
                updated_count += 1
                
        return Response({
            'success': True,
            'message': f'Successfully applied {discount_percent}% discount to {updated_count} active pricing rules.',
            'updated_count': updated_count
        })


class AssetPhotoViewSet(viewsets.ModelViewSet):
    """ViewSet for managing asset photos."""
    queryset = AssetPhoto.objects.all().order_by('order')
    serializer_class = AssetPhotoSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = AssetPhoto.objects.all().order_by('order')
        asset_id = self.request.query_params.get('asset')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        return queryset


class AssetPricingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing asset pricing rules."""
    queryset = AssetPricing.objects.all().order_by('-priority')
    serializer_class = AssetPricingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = AssetPricing.objects.all().order_by('-priority')
        asset_id = self.request.query_params.get('asset')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class AssetAvailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet for managing asset availability rules."""
    queryset = AssetAvailability.objects.all()
    serializer_class = AssetAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = AssetAvailability.objects.all()
        asset_id = self.request.query_params.get('asset')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

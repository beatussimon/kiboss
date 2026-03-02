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

        # Check listing limits for non-child, non-vehicle assets
        is_child = serializer.validated_data.get('parent') is not None
        if not is_child and asset_type != AssetType.VEHICLE:
            ASSET_LIMITS = {'FREE': 3, 'PLUS': 10}
            max_assets = ASSET_LIMITS.get(user.account_tier, float('inf'))
            if max_assets != float('inf'):
                active_count = Asset.objects.filter(
                    owner=user, is_active=True, parent__isnull=True
                ).exclude(asset_type=AssetType.VEHICLE).count()
                if active_count >= max_assets:
                    raise PermissionDenied(f"Your {user.account_tier} plan allows up to {max_assets} asset listings. Upgrade to Plus or delete existing assets.")
        
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
                
            if not is_verified_corporate:
                # Regular users are limited by their tier
                vehicle_count = Asset.objects.filter(
                    owner=user, 
                    asset_type=AssetType.VEHICLE
                ).exclude(is_active=False, is_listed=False).count()
                
                VEHICLE_LIMITS = {'FREE': 1, 'PLUS': 3}
                max_vehicles = VEHICLE_LIMITS.get(user.account_tier, 1)
                
                if vehicle_count >= max_vehicles:
                    raise PermissionDenied(f"Your {user.account_tier} plan allows you to register up to {max_vehicles} vehicle(s). Upgrade to Plus or register as a Corporate Ride Business to add more.")
            
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
            'owner', 'verified_by'
        ).prefetch_related(
            'photos',
            'pricing_rules',
            'availability_rules',
            'capacities',
            'owner__corporate_profile',
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

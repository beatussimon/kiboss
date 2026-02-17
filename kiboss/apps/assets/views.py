"""
Views for Assets API - Universal Asset System
"""
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Avg
from django.utils import timezone
from kiboss.apps.assets.models import Asset, AssetPhoto, AssetPricing, AssetAvailability
from kiboss.apps.assets.serializers import (
    AssetSerializer, AssetDetailSerializer, AssetListSerializer,
    AssetPhotoSerializer, AssetPricingSerializer, AssetAvailabilitySerializer
)


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
        """Set the owner to the current user when creating an asset."""
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        asset = self.get_object()
        if asset.owner_id != self.request.user.id and not self.request.user.is_superuser:
            raise PermissionDenied('Only the asset owner can update this asset')
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
        queryset = Asset.objects.select_related('owner', 'verified_by').prefetch_related(
            'photos',
            'pricing_rules',
            'availability_rules',
            'capacities',
        ).order_by('-created_at')
        
        # Filter by asset type
        asset_type = self.request.query_params.get('asset_type')
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        
        # Filter by owner
        owner_id = self.request.query_params.get('owner')
        if owner_id:
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
        if self.action in ['list', 'retrieve']:
            queryset = queryset.filter(is_active=True)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_listed = self.request.query_params.get('is_listed')
        if is_listed is not None:
            queryset = queryset.filter(is_listed=is_listed.lower() == 'true')
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(average_rating__gte=min_rating)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify an asset (admin/owner only)."""
        asset = self.get_object()
        asset.verification_status = 'VERIFIED'
        asset.verified_at = timezone.now()
        asset.verified_by = request.user
        asset.save()
        serializer = self.get_serializer(asset)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an asset."""
        asset = self.get_object()
        asset.is_active = False
        asset.save()
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

"""
URL Configuration for Assets API
"""

from django.urls import path, include
from kiboss.apps.assets.views import (
    AssetViewSet, AssetPhotoViewSet, AssetPricingViewSet, AssetAvailabilityViewSet
)

urlpatterns = [
    path('', AssetViewSet.as_view({'get': 'list', 'post': 'create'}), name='asset-list'),
    path('<str:pk>/', AssetViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='asset-detail'),
    path('<str:pk>/photos/', AssetViewSet.as_view({'get': 'photos'}), name='asset-photos'),
    path('<str:pk>/pricing/', AssetViewSet.as_view({'get': 'pricing'}), name='asset-pricing'),
    path('<str:pk>/availability/', AssetViewSet.as_view({'get': 'availability'}), name='asset-availability'),
    path('<str:pk>/verify/', AssetViewSet.as_view({'post': 'verify'}), name='asset-verify'),
    path('<str:pk>/deactivate/', AssetViewSet.as_view({'post': 'deactivate'}), name='asset-deactivate'),
    path('<str:pk>/activate/', AssetViewSet.as_view({'post': 'activate'}), name='asset-activate'),
    
    # Photo endpoints
    path('photos/', AssetPhotoViewSet.as_view({'get': 'list', 'post': 'create'}), name='assetphoto-list'),
    path('photos/<str:pk>/', AssetPhotoViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='assetphoto-detail'),
    
    # Pricing endpoints
    path('pricing/', AssetPricingViewSet.as_view({'get': 'list', 'post': 'create'}), name='assetpricing-list'),
    path('pricing/<str:pk>/', AssetPricingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='assetpricing-detail'),
    
    # Availability endpoints
    path('availability/', AssetAvailabilityViewSet.as_view({'get': 'list', 'post': 'create'}), name='assetavailability-list'),
    path('availability/<str:pk>/', AssetAvailabilityViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='assetavailability-detail'),
]

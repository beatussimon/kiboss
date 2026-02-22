"""
URL Configuration for Assets API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.assets.views import (
    AssetViewSet, AssetPhotoViewSet, AssetPricingViewSet, AssetAvailabilityViewSet
)

router = DefaultRouter()
router.register(r'photos', AssetPhotoViewSet, basename='assetphoto')
router.register(r'pricing', AssetPricingViewSet, basename='assetpricing')
router.register(r'availability', AssetAvailabilityViewSet, basename='assetavailability')
router.register(r'', AssetViewSet, basename='asset')

urlpatterns = [
    path('', include(router.urls)),
]

"""URL Configuration for Payments API"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.payments.views import PaymentViewSet, DisputeViewSet

router = DefaultRouter()
router.register(r'', PaymentViewSet, basename='payment')
router.register(r'disputes', DisputeViewSet, basename='dispute')

urlpatterns = [
    path('', include(router.urls)),
]

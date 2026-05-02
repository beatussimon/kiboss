"""
URL Configuration for Booking API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.bookings.views import BookingViewSet, VenueQuoteViewSet

router = DefaultRouter()
router.register('venue-quotes', VenueQuoteViewSet, basename='venue-quote')
router.register('', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
]

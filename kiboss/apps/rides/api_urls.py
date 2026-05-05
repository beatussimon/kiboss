"""
URL Configuration for Rides API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.rides.views import (
    RideViewSet, RideStopViewSet, SeatBookingViewSet, RideScheduleViewSet,
    VehicleRegistrationViewSet, CargoBookingViewSet
)
from kiboss.apps.rides.promoted_view import PromotedRideViewSet

router = DefaultRouter()
# Specific entities
router.register(r'vehicles', VehicleRegistrationViewSet, basename='vehicle-registration')
router.register(r'stops', RideStopViewSet, basename='ridestop')
router.register(r'bookings', SeatBookingViewSet, basename='seatbooking')
router.register(r'cargo-bookings', CargoBookingViewSet, basename='cargobooking')
router.register(r'schedules', RideScheduleViewSet, basename='rideschedule')
router.register(r'promoted', PromotedRideViewSet, basename='promotedride')
# Base resource
router.register(r'trips', RideViewSet, basename='ride')

urlpatterns = [
    path('', include(router.urls)),
]

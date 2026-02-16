"""
URL Configuration for Rides API
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter
from kiboss.apps.rides.views import (
    RideViewSet, RideStopViewSet, SeatBookingViewSet, RideScheduleViewSet
)

router = SimpleRouter()
router.register(r'', RideViewSet, basename='ride')
router.register(r'stops', RideStopViewSet, basename='ridestop')
router.register(r'bookings', SeatBookingViewSet, basename='seatbooking')
router.register(r'schedules', RideScheduleViewSet, basename='rideschedule')

urlpatterns = [
    path('', include(router.urls)),
]

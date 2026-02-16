"""URL Configuration for Rides API"""

from django.urls import path, include

urlpatterns = [
    path('', include('kiboss.apps.rides.api_urls')),
]

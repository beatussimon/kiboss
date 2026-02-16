"""URL Configuration for Notifications API"""

from django.urls import path, include

urlpatterns = [
    path('', include('kiboss.apps.notifications.api_urls')),
]

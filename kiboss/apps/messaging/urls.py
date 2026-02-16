"""URL Configuration for Messaging API"""

from django.urls import path, include

urlpatterns = [
    path('', include('kiboss.apps.messaging.api_urls')),
]

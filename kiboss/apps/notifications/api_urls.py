"""
URL Configuration for Notifications API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.notifications.views import NotificationViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='preference')

urlpatterns = [
    path('', include(router.urls)),
]

"""
URL Configuration for Tasks API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.tasks.views import StaffTaskViewSet

router = DefaultRouter()
router.register(r'', StaffTaskViewSet, basename='stafftask')

urlpatterns = [
    path('', include(router.urls)),
]

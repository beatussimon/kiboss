"""URL Configuration for Contracts API"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.contracts.views import ContractViewSet

router = DefaultRouter()
router.register(r'', ContractViewSet, basename='contract')

urlpatterns = [
    path('', include(router.urls)),
]

"""
URL Configuration for Assets API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.assets.api_urls import urlpatterns as api_urlpatterns

urlpatterns = api_urlpatterns

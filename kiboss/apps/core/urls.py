"""URL Configuration for Core App"""
from django.urls import path
from kiboss.apps.core.views import PublicSettingsView, health_check

urlpatterns = [
    path('settings/', PublicSettingsView.as_view(), name='public-settings'),
    path('health/', health_check, name='health-check'),
]

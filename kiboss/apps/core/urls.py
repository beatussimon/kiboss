"""URL Configuration for Core App"""
from django.urls import path
from kiboss.apps.core.views import PublicSettingsView

urlpatterns = [
    path('settings/', PublicSettingsView.as_view(), name='public-settings'),
]

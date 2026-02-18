"""
URL configuration for Common API
"""

from django.urls import path
from kiboss.apps.common.services.location import LocationView


urlpatterns = [
    path('location/search/', LocationView.as_view(), name='location-search'),
    path('location/nearby/rides/', LocationView.as_view(), name='nearby-rides'),
    path('location/nearby/assets/', LocationView.as_view(), name='nearby-assets'),
    path('location/suggest/', LocationView.as_view(), name='location-suggest'),
]


# Include these URLs in the main URL configuration:
# path('api/common/', include('kiboss.apps.common.urls')),
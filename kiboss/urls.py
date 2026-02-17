"""
URL configuration for kiboss project.

KIBOSS - Universal Rental & Sharing Operating System
"""

from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Use custom admin site
from kiboss.apps.core.admin import admin_site


def api_root(request):
    """API root endpoint - returns available resources."""
    return JsonResponse(
        {
            'status': 'ok',
            'name': 'KIBOSS API',
            'version': 'v1',
            'documentation': '/api/v1/docs/',
            'schema': '/api/v1/schema/',
            'resources': {
                'auth': '/api/v1/auth/',
                'users': '/api/v1/users/',
                'assets': '/api/v1/assets/',
                'bookings': '/api/v1/bookings/',
                'contracts': '/api/v1/contracts/',
                'payments': '/api/v1/payments/',
                'rides': '/api/v1/rides/',
                'messages': '/api/v1/messaging/',
                'ratings': '/api/v1/ratings/',
                'notifications': '/api/v1/notifications/',
                'social': '/api/v1/social/',
                'rbac': '/api/v1/rbac/',
                'audits': '/api/v1/audits/',
            },
        },
        json_dumps_params={'separators': (',', ':')},
    )


urlpatterns = [
    # Admin - using custom admin site with dashboard
    path('admin/', admin_site.urls),
    
    # API v1 - Root
    path('api/v1/', api_root, name='api-root'),
    
    # API v1 - Root
    path('api/v1/', api_root, name='api-root'),
    
    # API v1 - JWT Authentication (from users app)
    path('api/v1/auth/', include('kiboss.apps.users.urls')),
    
    # API v1 - Schema
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    
    # API v1 - KIBOSS Apps
    path('api/v1/users/', include('kiboss.apps.users.urls')),
    path('api/v1/assets/', include('kiboss.apps.assets.urls')),
    path('api/v1/bookings/', include('kiboss.apps.bookings.urls')),
    path('api/v1/contracts/', include('kiboss.apps.contracts.urls')),
    path('api/v1/payments/', include('kiboss.apps.payments.urls')),
    path('api/v1/rides/', include('kiboss.apps.rides.urls')),
    path('api/v1/messaging/', include('kiboss.apps.messaging.urls')),
    path('api/v1/ratings/', include('kiboss.apps.ratings.urls')),
    path('api/v1/notifications/', include('kiboss.apps.notifications.urls')),
    path('api/v1/social/', include('kiboss.apps.social.urls')),
    path('api/v1/rbac/', include('kiboss.apps.rbac.urls')),
    path('api/v1/audits/', include('kiboss.apps.audits.urls')),
]

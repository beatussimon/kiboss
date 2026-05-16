"""
Public API views for core app settings (e.g., hero image for landing page).
"""
from django.conf import settings as django_settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from kiboss.apps.core.models import SystemConfiguration


class PublicSettingsView(APIView):
    """
    Public endpoint returning global settings readable by the frontend.
    No authentication required.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        config = SystemConfiguration.get_config()

        # Hero image: URL takes priority over uploaded image
        hero_image = None
        if config.hero_image_url:
            hero_image = config.hero_image_url
        elif config.hero_image:
            hero_image = request.build_absolute_uri(config.hero_image.url)

        return Response({
            'hero_image': hero_image,
        })


def health_check(request):
    """
    Simple health check endpoint for monitoring.
    """
    from django.db import connections
    from django.db.utils import OperationalError
    from django.http import JsonResponse
    
    db_conn = connections['default']
    try:
        db_conn.cursor()
    except OperationalError:
        return JsonResponse({"status": "unhealthy", "database": "unavailable"}, status=503)
    
    return JsonResponse({"status": "healthy"})

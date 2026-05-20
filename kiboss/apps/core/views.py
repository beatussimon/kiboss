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
    Comprehensive health check endpoint for DB, Redis, and Celery.
    """
    from django.db import connections
    from django.db.utils import OperationalError
    from django.http import JsonResponse
    from django.core.cache import cache
    import logging
    
    logger = logging.getLogger(__name__)
    
    health_status = {
        "status": "healthy",
        "database": "healthy",
        "redis": "healthy",
        "celery": "healthy"
    }
    status_code = 200

    # 1. Check Database
    try:
        db_conn = connections['default']
        db_conn.cursor()
    except Exception as e:
        logger.error(f"DB Health Check failed: {e}")
        health_status["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        status_code = 503
        
    # 2. Check Redis (Cache)
    try:
        cache.set('health_check', 'ok', timeout=1)
        if cache.get('health_check') != 'ok':
            raise Exception("Cache retrieval mismatch")
    except Exception as e:
        logger.error(f"Redis Health Check failed: {e}")
        health_status["redis"] = "unhealthy"
        health_status["status"] = "unhealthy"
        status_code = 503
            
    # 3. Check Celery Workers
    try:
        from kiboss.celery import app as celery_app
        inspector = celery_app.control.inspect(timeout=0.5)
        stats = inspector.stats()
        if not stats:
            health_status["celery"] = "unavailable"
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Celery Health Check failed: {e}")
        health_status["celery"] = "unhealthy"
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"
        
    return JsonResponse(health_status, status=status_code)

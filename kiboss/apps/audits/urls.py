from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.audits.views import AuditLogViewSet

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

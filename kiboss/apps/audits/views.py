from rest_framework import viewsets, permissions
from kiboss.apps.audits.models import AuditLog
from kiboss.apps.audits.serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]

from rest_framework import viewsets, permissions
from kiboss.apps.rbac.models import UserRole, RolePermission, AdminAction
from kiboss.apps.rbac.serializers import UserRoleSerializer, RolePermissionSerializer, AdminActionSerializer

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAdminUser]

class RolePermissionViewSet(viewsets.ModelViewSet):
    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer
    permission_classes = [permissions.IsAdminUser]

class AdminActionViewSet(viewsets.ModelViewSet):
    queryset = AdminAction.objects.all()
    serializer_class = AdminActionSerializer
    permission_classes = [permissions.IsAdminUser]

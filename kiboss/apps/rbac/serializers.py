from rest_framework import serializers
from kiboss.apps.rbac.models import UserRole, RolePermission, AdminAction

class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = '__all__'

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'

class AdminActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminAction
        fields = '__all__'

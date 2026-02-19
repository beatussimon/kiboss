from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.rbac.views import UserRoleViewSet, RolePermissionViewSet, AdminActionViewSet

router = DefaultRouter()
router.register(r'user-roles', UserRoleViewSet)
router.register(r'role-permissions', RolePermissionViewSet)
router.register(r'admin-actions', AdminActionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

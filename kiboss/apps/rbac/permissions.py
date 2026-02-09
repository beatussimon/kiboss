"""
RBAC Permissions for KIBOSS

Role-Based Access Control implementation with:
- Role permissions
- Object-level permissions
- Scope-based access
- Justification requirements for admin actions
"""

from rest_framework import permissions
from django.db.models import Q
from django.utils import timezone
from kiboss.apps.rbac.models import Role, Permission, UserRole


class RoleBasedPermission(permissions.BasePermission):
    """
    Role-based permission class for KIBOSS.
    
    Checks user roles and permissions before allowing access.
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admins have all permissions
        if request.user.is_superuser:
            return True
        
        # Get required permission from view
        required_permission = getattr(view, 'required_permission', None)
        
        if not required_permission:
            # No specific permission required
            return True
        
        # Check if user has the required permission
        return self._has_permission(request.user, required_permission)
    
    def has_object_permission(self, request, view, obj):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admins have all object permissions
        if request.user.is_superuser:
            return True
        
        # Get required object permission from view
        required_object_permission = getattr(
            view, 'required_object_permission', None
        )
        
        if not required_object_permission:
            # No specific object permission required
            return True
        
        # Check object-level permission
        return self._has_object_permission(
            request.user, required_object_permission, obj
        )
    
    def _has_permission(self, user, permission):
        """Check if user has specific permission through their roles."""
        # Get user's active roles
        user_roles = UserRole.objects.filter(
            user=user
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        
        role_codes = user_roles.values_list('role', flat=True)
        
        # Check if any role has the required permission
        from kiboss.apps.rbac.models import RolePermission
        return RolePermission.objects.filter(
            role__in=role_codes,
            permission=permission
        ).exists()
    
    def _has_object_permission(self, user, permission, obj):
        """Check object-level permission with scope."""
        # Check ownership first
        if hasattr(obj, 'owner') and obj.owner_id == user.id:
            return True
        
        if hasattr(obj, 'renter') and obj.renter_id == user.id:
            return True
        
        # Check role scope
        user_roles = UserRole.objects.filter(
            user=user,
            scope_type=obj.__class__.__name__.upper(),
            scope_id=obj.id
        ).exists()
        
        if user_roles:
            return True
        
        # Check global permission for the resource type
        return self._has_permission(
            user,
            f"{permission}_{obj.__class__.__name__.upper()}"
        )


class IsSuperAdmin(permissions.BasePermission):
    """Allow only super admins."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow owners to edit, others to read only."""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for owner
        if hasattr(obj, 'owner'):
            return obj.owner_id == request.user.id
        
        if hasattr(obj, 'user'):
            return obj.user_id == request.user.id
        
        return False


class IsParticipant(permissions.BasePermission):
    """Allow only thread participants."""
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'participants'):
            return request.user in obj.participants.all()
        
        return False


class IsRenterOrOwner(permissions.BasePermission):
    """Allow only renter or owner of booking."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        # Check if user is renter or owner
        if hasattr(obj, 'renter') and obj.renter == request.user:
            return True
        
        if hasattr(obj, 'asset') and obj.asset.owner == request.user:
            return True
        
        return False


class ContractAcceptancePermission(permissions.BasePermission):
    """Permission for contract acceptance."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        # Check if user is a party to the contract
        booking = obj.booking
        
        if booking.renter == request.user:
            return True
        
        if booking.asset.owner == request.user:
            return True
        
        return False


class NotificationPreferencePermission(permissions.BasePermission):
    """Permission for notification preferences."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # Users can only edit their own preferences
        return obj.user_id == request.user.id


class JustificationRequired(permissions.BasePermission):
    """
    Permission that requires justification for admin actions.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Check if this is an admin action
        if not hasattr(view, 'requires_justification'):
            return True
        
        if not view.requires_justification:
            return True
        
        # Check if justification is provided
        justification = request.data.get('justification', '')
        if not justification:
            return False
        
        return True


# Permission constants for convenience
class Perm:
    """Permission constants."""
    
    # Users
    USER_VIEW = 'USER_VIEW'
    USER_CREATE = 'USER_CREATE'
    USER_EDIT = 'USER_EDIT'
    USER_DELETE = 'USER_DELETE'
    USER_BAN = 'USER_BAN'
    USER_VERIFY = 'USER_VERIFY'
    
    # Assets
    ASSET_VIEW = 'ASSET_VIEW'
    ASSET_CREATE = 'ASSET_CREATE'
    ASSET_EDIT = 'ASSET_EDIT'
    ASSET_DELETE = 'ASSET_DELETE'
    ASSET_VERIFY = 'ASSET_VERIFY'
    ASSET_REJECT = 'ASSET_REJECT'
    
    # Bookings
    BOOKING_VIEW = 'BOOKING_VIEW'
    BOOKING_EDIT = 'BOOKING_EDIT'
    BOOKING_CANCEL = 'BOOKING_CANCEL'
    BOOKING_OVERRIDE = 'BOOKING_OVERRIDE'
    
    # Contracts
    CONTRACT_VIEW = 'CONTRACT_VIEW'
    CONTRACT_EDIT = 'CONTRACT_EDIT'
    CONTRACT_OVERRIDE = 'CONTRACT_OVERRIDE'
    
    # Payments
    PAYMENT_VIEW = 'PAYMENT_VIEW'
    PAYMENT_EDIT = 'PAYMENT_EDIT'
    PAYMENT_REFUND = 'PAYMENT_REFUND'
    PAYMENT_OVERRIDE = 'PAYMENT_OVERRIDE'
    
    # Disputes
    DISPUTE_VIEW = 'DISPUTE_VIEW'
    DISPUTE_RESOLVE = 'DISPUTE_RESOLVE'
    
    # Ratings
    RATING_VIEW = 'RATING_VIEW'
    RATING_MODERATE = 'RATING_MODERATE'
    
    # Messaging
    MESSAGE_VIEW = 'MESSAGE_VIEW'
    MESSAGE_MODERATE = 'MESSAGE_MODERATE'
    
    # Admin
    AUDIT_VIEW = 'AUDIT_VIEW'
    SETTINGS_EDIT = 'SETTINGS_EDIT'
    ROLE_MANAGE = 'ROLE_MANAGE'

# RBAC Permission Matrix for KIBOSS

This document defines the Role-Based Access Control (RBAC) system for KIBOSS.

---

## 1. Roles Overview

### 1.1 System Roles

| Role | Description | Scope |
|------|-------------|-------|
| **SUPER_ADMIN** | Full system access | Global |
| **OPS** | Operations management | Global |
| **SUPPORT** | Customer support | Global |
| **FINANCE** | Financial operations | Global |
| **LEGAL** | Legal compliance | Global |
| **MODERATOR** | Content moderation | Global |
| **VERIFIER** | Asset/user verification | Global |
| **OWNER** | Asset owners | Own assets |
| **RENTER** | Platform renters | Own bookings |
| **DRIVER** | Ride-sharing drivers | Own rides |

### 1.2 Role Hierarchy

```
SUPER_ADMIN (top)
    ├── OPS
    │       ├── SUPPORT
    │       ├── FINANCE
    │       ├── LEGAL
    │       └── MODERATOR
    └── VERIFIER
```

---

## 2. Permission Definitions

### 2.1 User Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Users | `USER_VIEW` | View user profiles |
| Create Users | `USER_CREATE` | Create new users |
| Edit Users | `USER_EDIT` | Edit user profiles |
| Delete Users | `USER_DELETE` | Delete user accounts |
| Ban Users | `USER_BAN` | Ban/unban users |
| Verify Users | `USER_VERIFY` | Verify user identity |

### 2.2 Asset Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Assets | `ASSET_VIEW` | View asset listings |
| Create Assets | `ASSET_CREATE` | Create new assets |
| Edit Assets | `ASSET_EDIT` | Edit own assets |
| Delete Assets | `ASSET_DELETE` | Delete own assets |
| Verify Assets | `ASSET_VERIFY` | Verify asset listings |
| Reject Assets | `ASSET_REJECT` | Reject asset listings |

### 2.3 Booking Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Bookings | `BOOKING_VIEW` | View bookings |
| Edit Bookings | `BOOKING_EDIT` | Edit bookings |
| Cancel Bookings | `BOOKING_CANCEL` | Cancel bookings |
| Override Bookings | `BOOKING_OVERRIDE` | Admin booking overrides |

### 2.4 Contract Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Contracts | `CONTRACT_VIEW` | View contracts |
| Edit Contracts | `CONTRACT_EDIT` | Edit contracts |
| Override Contracts | `CONTRACT_OVERRIDE` | Admin contract overrides |

### 2.5 Payment Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Payments | `PAYMENT_VIEW` | View payment records |
| Edit Payments | `PAYMENT_EDIT` | Edit payment records |
| Refund Payments | `PAYMENT_REFUND` | Process refunds |
| Override Payments | `PAYMENT_OVERRIDE` | Admin payment overrides |

### 2.6 Dispute Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Disputes | `DISPUTE_VIEW` | View disputes |
| Resolve Disputes | `DISPUTE_RESOLVE` | Resolve disputes |

### 2.7 Rating Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Ratings | `RATING_VIEW` | View ratings |
| Moderate Ratings | `RATING_MODERATE` | Moderate ratings |

### 2.8 Messaging Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Messages | `MESSAGE_VIEW` | View messages |
| Moderate Messages | `MESSAGE_MODERATE` | Moderate messages |

### 2.9 Admin Permissions

| Permission | Code | Description |
|------------|------|-------------|
| View Audit Logs | `AUDIT_VIEW` | View audit logs |
| Edit Settings | `SETTINGS_EDIT` | Edit system settings |
| Manage Roles | `ROLE_MANAGE` | Assign roles |

---

## 3. Permission Matrix

### 3.1 Super Admin

| Permission | Access |
|------------|--------|
| USER_VIEW | ✓ |
| USER_CREATE | ✓ |
| USER_EDIT | ✓ |
| USER_DELETE | ✓ |
| USER_BAN | ✓ |
| USER_VERIFY | ✓ |
| ASSET_VIEW | ✓ |
| ASSET_CREATE | ✓ (all assets) |
| ASSET_EDIT | ✓ (all assets) |
| ASSET_DELETE | ✓ (all assets) |
| ASSET_VERIFY | ✓ |
| ASSET_REJECT | ✓ |
| BOOKING_VIEW | ✓ |
| BOOKING_EDIT | ✓ (all bookings) |
| BOOKING_CANCEL | ✓ |
| BOOKING_OVERRIDE | ✓ |
| CONTRACT_VIEW | ✓ |
| CONTRACT_EDIT | ✓ |
| CONTRACT_OVERRIDE | ✓ |
| PAYMENT_VIEW | ✓ |
| PAYMENT_EDIT | ✓ |
| PAYMENT_REFUND | ✓ |
| PAYMENT_OVERRIDE | ✓ |
| DISPUTE_VIEW | ✓ |
| DISPUTE_RESOLVE | ✓ |
| RATING_VIEW | ✓ |
| RATING_MODERATE | ✓ |
| MESSAGE_VIEW | ✓ |
| MESSAGE_MODERATE | ✓ |
| AUDIT_VIEW | ✓ |
| SETTINGS_EDIT | ✓ |
| ROLE_MANAGE | ✓ |

### 3.2 Ops

| Permission | Access |
|------------|--------|
| USER_VIEW | ✓ |
| USER_EDIT | Limited |
| ASSET_VIEW | ✓ |
| ASSET_EDIT | ✓ |
| ASSET_VERIFY | ✓ |
| ASSET_REJECT | ✓ |
| BOOKING_VIEW | ✓ |
| BOOKING_EDIT | ✓ |
| BOOKING_CANCEL | ✓ |
| CONTRACT_VIEW | ✓ |
| CONTRACT_EDIT | ✓ |
| PAYMENT_VIEW | ✓ |
| DISPUTE_VIEW | ✓ |
| DISPUTE_RESOLVE | ✓ |
| RATING_VIEW | ✓ |
| MESSAGE_VIEW | ✓ |
| AUDIT_VIEW | ✓ |

### 3.3 Support

| Permission | Access |
|------------|--------|
| USER_VIEW | ✓ (limited fields) |
| ASSET_VIEW | ✓ |
| BOOKING_VIEW | ✓ |
| BOOKING_CANCEL | Own bookings only |
| CONTRACT_VIEW | ✓ |
| PAYMENT_VIEW | Limited |
| DISPUTE_VIEW | ✓ |
| DISPUTE_RESOLVE | Limited |
| RATING_VIEW | ✓ |
| MESSAGE_VIEW | ✓ |

### 3.4 Finance

| Permission | Access |
|------------|--------|
| USER_VIEW | Limited |
| ASSET_VIEW | ✓ |
| BOOKING_VIEW | ✓ |
| CONTRACT_VIEW | ✓ |
| PAYMENT_VIEW | ✓ |
| PAYMENT_EDIT | ✓ |
| PAYMENT_REFUND | ✓ |
| DISPUTE_VIEW | ✓ |
| DISPUTE_RESOLVE | ✓ |
| AUDIT_VIEW | ✓ |

### 3.5 Legal

| Permission | Access |
|------------|--------|
| USER_VIEW | Limited |
| ASSET_VIEW | ✓ |
| BOOKING_VIEW | ✓ |
| CONTRACT_VIEW | ✓ |
| CONTRACT_OVERRIDE | ✓ |
| PAYMENT_VIEW | ✓ |
| DISPUTE_VIEW | ✓ |
| DISPUTE_RESOLVE | ✓ |
| AUDIT_VIEW | ✓ |

### 3.6 Moderator

| Permission | Access |
|------------|--------|
| USER_VIEW | ✓ |
| ASSET_VIEW | ✓ |
| ASSET_REJECT | ✓ |
| BOOKING_VIEW | ✓ |
| CONTRACT_VIEW | ✓ |
| RATING_VIEW | ✓ |
| RATING_MODERATE | ✓ |
| MESSAGE_VIEW | ✓ |
| MESSAGE_MODERATE | ✓ |
| AUDIT_VIEW | Limited |

### 3.7 Verifier

| Permission | Access |
|------------|--------|
| USER_VIEW | ✓ |
| USER_VERIFY | ✓ |
| ASSET_VIEW | ✓ |
| ASSET_VERIFY | ✓ |
| ASSET_REJECT | ✓ |
| BOOKING_VIEW | ✓ |
| CONTRACT_VIEW | ✓ |

### 3.8 Owner

| Permission | Access |
|------------|--------|
| USER_VIEW | Public profiles only |
| ASSET_VIEW | ✓ (all) |
| ASSET_CREATE | ✓ (own) |
| ASSET_EDIT | Own assets only |
| ASSET_DELETE | Own assets only |
| BOOKING_VIEW | Bookings for own assets |
| BOOKING_CANCEL | Own bookings only |
| CONTRACT_VIEW | Contracts for own assets |
| CONTRACT_EDIT | Limited |
| PAYMENT_VIEW | Payments for own assets |
| DISPUTE_VIEW | Disputes for own assets |
| RATING_VIEW | Ratings for own assets |
| MESSAGE_VIEW | Related threads |

### 3.9 Renter

| Permission | Access |
|------------|--------|
| USER_VIEW | Public profiles only |
| ASSET_VIEW | ✓ |
| ASSET_CREATE | ✗ |
| ASSET_EDIT | ✗ |
| ASSET_DELETE | ✗ |
| BOOKING_VIEW | Own bookings only |
| BOOKING_EDIT | Own bookings only |
| BOOKING_CANCEL | Own bookings only |
| CONTRACT_VIEW | Own contracts only |
| CONTRACT_EDIT | ✗ |
| PAYMENT_VIEW | Own payments only |
| DISPUTE_VIEW | Own disputes only |
| DISPUTE_RESOLVE | Own disputes only |
| RATING_VIEW | Related ratings |
| RATING_MODERATE | ✗ |
| MESSAGE_VIEW | Related threads |

### 3.10 Driver

| Permission | Access |
|------------|--------|
| USER_VIEW | Public profiles only |
| ASSET_VIEW | ✓ (vehicles) |
| ASSET_CREATE | Own vehicles only |
| ASSET_EDIT | Own vehicles only |
| RIDE_VIEW | ✓ |
| RIDE_CREATE | ✓ (own) |
| RIDE_EDIT | Own rides only |
| RIDE_DELETE | Own rides only |
| SEAT_VIEW | Own rides |
| SEAT_EDIT | Own rides |
| BOOKING_VIEW | Bookings for own rides |
| CONTRACT_VIEW | Contracts for own rides |
| PAYMENT_VIEW | Payments for own rides |
| RATING_VIEW | Ratings for own rides |
| MESSAGE_VIEW | Related threads |

---

## 4. Scope Limitations

### 4.1 Asset Scoped Roles

Roles can be limited to specific assets:

```python
# Example: Support role limited to specific assets
user_role = UserRole.objects.create(
    user=user,
    role=Role.SUPPORT,
    scope_type='ASSET',
    scope_id=asset_id,
    expires_at=timezone.now() + timedelta(days=30)
)
```

### 4.2 Jurisdiction Scoped Roles

Roles can be limited to specific jurisdictions:

```python
# Example: Moderator role limited to US-NY jurisdiction
user_role = UserRole.objects.create(
    user=user,
    role=Role.MODERATOR,
    scope_type='JURISDICTION',
    scope_id='US-NY'
)
```

### 4.3 Time-Limited Roles

Roles can have expiration:

```python
# Example: Temporary admin access
user_role = UserRole.objects.create(
    user=user,
    role=Role.OPS,
    expires_at=timezone.now() + timedelta(days=7)
)
```

---

## 5. Implementation

### 5.1 Permission Decorator

```python
# kiboss/apps/rbac/permissions.py

from rest_framework import permissions
from kiboss.apps.rbac.models import Permission, RolePermission


class RoleBasedPermission(permissions.BasePermission):
    """
    Role-based permission class.
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admins have all permissions
        if request.user.is_superuser:
            return True
        
        # Check role-based permissions
        required_permission = getattr(view, 'required_permission', None)
        
        if required_permission:
            return self._has_permission(request.user, required_permission)
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Check object-level permissions
        required_permission = getattr(view, 'required_object_permission', None)
        
        if required_permission:
            return self._has_object_permission(request.user, required_permission, obj)
        
        return True
    
    def _has_permission(self, user, permission):
        """Check if user has specific permission."""
        # Get user's roles
        user_roles = user.user_roles.filter(
            models.Q(expires_at__isnull=True) |
            models.Q(expires_at__gt=timezone.now())
        )
        
        # Check each role for permission
        role_codes = user_roles.values_list('role', flat=True)
        
        return RolePermission.objects.filter(
            role__in=role_codes,
            permission=permission
        ).exists()
    
    def _has_object_permission(self, user, permission, obj):
        """Check object-level permission with scope."""
        # Check ownership or scope
        if hasattr(obj, 'owner') and obj.owner_id == user.id:
            return True
        
        # Check role scope
        user_roles = user.user_roles.filter(
            scope_type=obj.__class__.__name__.upper(),
            scope_id=obj.id
        ).exists()
        
        return user_roles
```

### 5.2 View-Level Permission

```python
# Usage example in views

from kiboss.apps.rbac.permissions import RoleBasedPermission


class UserListView(APIView):
    """
    List all users (Admin only).
    """
    required_permission = 'USER_VIEW'
    permission_classes = [RoleBasedPermission]
    
    def get(self, request):
        # Only users with USER_VIEW can access
        ...


class AssetVerifyView(APIView):
    """
    Verify an asset (Verifier role only).
    """
    required_permission = 'ASSET_VERIFY'
    permission_classes = [RoleBasedPermission]
    
    def post(self, request, asset_id):
        # Only verifiers can access
        ...
```

### 5.3 Object-Level Permission

```python
class BookingDetailView(APIView):
    """
    View booking details.
    """
    required_permission = 'BOOKING_VIEW'
    required_object_permission = 'BOOKING_VIEW'
    permission_classes = [RoleBasedPermission]
    
    def get_object(self, request, booking_id):
        booking = Booking.objects.get(id=booking_id)
        
        # Check if user has permission for this specific booking
        if not self.has_object_permission(request, self, booking):
            raise PermissionDenied()
        
        return booking
```

---

## 6. Justification Requirements

### 6.1 Actions Requiring Justification

| Action | Justification Required |
|--------|----------------------|
| User Ban | ✓ |
| Booking Override | ✓ |
| Contract Override | ✓ |
| Payment Override | ✓ |
| Dispute Resolution | ✓ |
| Rating Moderation | ✓ |
| Message Moderation | ✓ |
| Asset Rejection | ✓ |
| User Unban | ✓ |

### 6.2 Justification Storage

```python
# Admin action with justification
AdminAction.objects.create(
    admin=request.user,
    action_type='BOOKING_OVERRIDE',
    resource_type='Booking',
    resource_id=booking_id,
    justification=request.data.get('justification'),
    old_value={'status': 'CONFIRMED'},
    new_value={'status': 'CANCELLED'},
    approved=True
)
```

---

## 7. Audit Logging

### 7.1 Audit Events

All permission changes are logged:

```python
# kiboss/apps/rbac/services.py

from kiboss.apps.audits.models import AuditLog, AuditAction


class AuditService:
    """Audit logging for RBAC operations."""
    
    @classmethod
    def log_role_assignment(cls, admin, user, role, justification):
        """Log role assignment."""
        AuditLog.log(
            actor=admin,
            action=AuditAction.PERMISSION_GRANTED,
            description=f"Assigned role {role} to user {user.id}",
            resource_type='User',
            resource_id=user.id,
            justification=justification,
            metadata={'role': role}
        )
    
    @classmethod
    def log_permission_override(cls, admin, action_type, resource, justification):
        """Log permission override."""
        AuditLog.log(
            actor=admin,
            action=AuditAction.PERMISSION_GRANTED,
            description=f"Override: {action_type}",
            resource_type=resource.__class__.__name__,
            resource_id=resource.id,
            justification=justification
        )
```

---

## 8. Default Role Assignments

### 8.1 Role Defaults

| User Type | Default Role | Scope |
|-----------|-------------|-------|
| New User | None (RENTER implied) | - |
| Asset Owner | OWNER | Own assets |
| Vehicle Owner + DRIVER | OWNER + DRIVER | Own assets/rides |
| Staff Member | Based on hiring | Global |

### 8.2 Role Assignment Workflow

```
1. User registers
       ↓
2. Profile verified (email)
       ↓
3. Identity verification (optional)
       ↓
4. Asset creation → OWNER role
       ↓
5. Vehicle verification → DRIVER role
       ↓
6. Staff onboarding → Appropriate role (by admin)
```

---

## 9. Security Considerations

### 9.1 Privilege Escalation Prevention

1. **Self-Assignment Forbidden**: Users cannot assign roles to themselves
2. **Higher Role Requirement**: Must have equal or higher role to assign
3. **Scope Verification**: Scope is validated before permission grant
4. **Audit Trail**: All role changes are audited

### 9.2 Regular Reviews

1. **Monthly Access Reviews**: OPS reviews active roles
2. **Quarterly Permission Audits**: Verify permission matrix
3. **Annual Role Cleanup**: Remove expired/inactive roles

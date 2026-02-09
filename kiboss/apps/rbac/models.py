"""
RBAC Models for KIBOSS - Role-Based Access Control

Roles:
- Super Admin
- Ops
- Support
- Finance
- Legal
- Moderator
- Verifier
"""

import uuid
from django.db import models
from django.conf import settings


class Role(models.TextChoices):
    """System roles."""
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    OPS = 'OPS', 'Operations'
    SUPPORT = 'SUPPORT', 'Support'
    FINANCE = 'FINANCE', 'Finance'
    LEGAL = 'LEGAL', 'Legal'
    MODERATOR = 'MODERATOR', 'Moderator'
    VERIFIER = 'VERIFIER', 'Verifier'


class Permission(models.TextChoices):
    """System permissions."""
    # Users
    USER_VIEW = 'USER_VIEW', 'View Users'
    USER_CREATE = 'USER_CREATE', 'Create Users'
    USER_EDIT = 'USER_EDIT', 'Edit Users'
    USER_DELETE = 'USER_DELETE', 'Delete Users'
    USER_BAN = 'USER_BAN', 'Ban Users'
    USER_VERIFY = 'USER_VERIFY', 'Verify Users'
    
    # Assets
    ASSET_VIEW = 'ASSET_VIEW', 'View Assets'
    ASSET_CREATE = 'ASSET_CREATE', 'Create Assets'
    ASSET_EDIT = 'ASSET_EDIT', 'Edit Assets'
    ASSET_DELETE = 'ASSET_DELETE', 'Delete Assets'
    ASSET_VERIFY = 'ASSET_VERIFY', 'Verify Assets'
    ASSET_REJECT = 'ASSET_REJECT', 'Reject Assets'
    
    # Bookings
    BOOKING_VIEW = 'BOOKING_VIEW', 'View Bookings'
    BOOKING_EDIT = 'BOOKING_EDIT', 'Edit Bookings'
    BOOKING_CANCEL = 'BOOKING_CANCEL', 'Cancel Bookings'
    BOOKING_OVERRIDE = 'BOOKING_OVERRIDE', 'Override Bookings'
    
    # Contracts
    CONTRACT_VIEW = 'CONTRACT_VIEW', 'View Contracts'
    CONTRACT_EDIT = 'CONTRACT_EDIT', 'Edit Contracts'
    CONTRACT_OVERRIDE = 'CONTRACT_OVERRIDE', 'Override Contracts'
    
    # Payments
    PAYMENT_VIEW = 'PAYMENT_VIEW', 'View Payments'
    PAYMENT_EDIT = 'PAYMENT_EDIT', 'Edit Payments'
    PAYMENT_REFUND = 'PAYMENT_REFUND', 'Refund Payments'
    PAYMENT_OVERRIDE = 'PAYMENT_OVERRIDE', 'Override Payments'
    
    # Disputes
    DISPUTE_VIEW = 'DISPUTE_VIEW', 'View Disputes'
    DISPUTE_RESOLVE = 'DISPUTE_RESOLVE', 'Resolve Disputes'
    
    # Ratings
    RATING_VIEW = 'RATING_VIEW', 'View Ratings'
    RATING_MODERATE = 'RATING_MODERATE', 'Moderate Ratings'
    
    # Messaging
    MESSAGE_VIEW = 'MESSAGE_VIEW', 'View Messages'
    MESSAGE_MODERATE = 'MESSAGE_MODERATE', 'Moderate Messages'
    
    # Admin
    AUDIT_VIEW = 'AUDIT_VIEW', 'View Audit Logs'
    SETTINGS_EDIT = 'SETTINGS_EDIT', 'Edit Settings'
    ROLE_MANAGE = 'ROLE_MANAGE', 'Manage Roles'


class RolePermission(models.Model):
    """Role-permission mapping."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices)
    permission = models.CharField(max_length=50, choices=Permission.choices)
    
    class Meta:
        db_table = 'role_permissions'
        unique_together = ['role', 'permission']
    
    def __str__(self):
        return f"{self.role}: {self.permission}"


class UserRole(models.Model):
    """User-role assignment."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    
    # Scope limitations (e.g., only for specific assets)
    scope_type = models.CharField(max_length=50, blank=True)
    scope_id = models.UUIDField(blank=True, null=True)
    
    # Expiry
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_user_roles'
    )
    
    class Meta:
        db_table = 'user_roles'
        unique_together = ['user', 'role', 'scope_type', 'scope_id']
    
    def __str__(self):
        return f"{self.user.email}: {self.role}"


class AdminAction(models.Model):
    """Record of admin actions requiring justification."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='admin_actions'
    )
    
    action_type = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.UUIDField()
    
    justification = models.TextField()
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    
    approved = models.BooleanField(default=True)
    approval_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_actions'
        verbose_name = 'Admin Action'
        verbose_name_plural = 'Admin Actions'
    
    def __str__(self):
        return f"Admin action: {self.action_type} on {self.resource_type}"

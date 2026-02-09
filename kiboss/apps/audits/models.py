"""
Audit Models for KIBOSS - Immutable Audit Logging

Features:
- Mandatory audit logs for all security-relevant events
- Immutable records
- Admin action tracking with justification
"""

import uuid
from django.db import models
from django.conf import settings


class AuditAction(models.TextChoices):
    """Audit action types."""
    # Authentication
    LOGIN = 'LOGIN', 'Login'
    LOGOUT = 'LOGOUT', 'Logout'
    LOGIN_FAILED = 'LOGIN_FAILED', 'Login Failed'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Change'
    TOKEN_REFRESH = 'TOKEN_REFRESH', 'Token Refresh'
    
    # Authorization
    PERMISSION_GRANTED = 'PERMISSION_GRANTED', 'Permission Granted'
    PERMISSION_REVOKED = 'PERMISSION_REVOKED', 'Permission Revoked'
    ROLE_CHANGED = 'ROLE_CHANGED', 'Role Changed'
    
    # Data Access
    DATA_EXPORT = 'DATA_EXPORT', 'Data Export'
    SENSITIVE_DATA_ACCESS = 'SENSITIVE_DATA_ACCESS', 'Sensitive Data Access'
    
    # Configuration
    SETTINGS_CHANGED = 'SETTINGS_CHANGED', 'Settings Changed'
    
    # Admin Actions
    USER_BANNED = 'USER_BANNED', 'User Banned'
    USER_UNBANNED = 'USER_UNBANNED', 'User Unbanned'
    USER_VERIFIED = 'USER_VERIFIED', 'User Verified'
    ASSET_VERIFIED = 'ASSET_VERIFIED', 'Asset Verified'
    ASSET_REJECTED = 'ASSET_REJECTED', 'Asset Rejected'
    BOOKING_OVERRIDE = 'BOOKING_OVERRIDE', 'Booking Override'
    CONTRACT_OVERRIDE = 'CONTRACT_OVERRIDE', 'Contract Override'
    PAYMENT_OVERRIDE = 'PAYMENT_OVERRIDE', 'Payment Override'
    DISPUTE_RESOLVED = 'DISPUTE_RESOLVED', 'Dispute Resolved'
    RATING_MODERATED = 'RATING_MODERATED', 'Rating Moderated'
    
    # System
    SYSTEM_ERROR = 'SYSTEM_ERROR', 'System Error'
    SECURITY_ALERT = 'SECURITY_ALERT', 'Security Alert'


class AuditLog(models.Model):
    """Immutable audit log model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Actor
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs'
    )
    actor_ip = models.GenericIPAddressField(blank=True, null=True)
    actor_user_agent = models.TextField(blank=True)
    
    # Action
    action = models.CharField(max_length=50, choices=AuditAction.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.UUIDField(blank=True, null=True)
    
    # Details
    description = models.TextField()
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    
    # Justification (required for admin actions)
    justification = models.TextField(blank=True)
    
    # Request context
    request_id = models.UUIDField(blank=True, null=True)
    trace_id = models.UUIDField(blank=True, null=True)
    
    # Result
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Audit {self.id}: {self.action} by {self.actor_id}"
    
    @classmethod
    def log(cls, actor, action, description, resource_type=None, resource_id=None,
            old_value=None, new_value=None, justification=None, success=True,
            error_message=None, metadata=None, request_id=None):
        """Create an audit log entry."""
        return cls.objects.create(
            actor=actor,
            action=action,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value or {},
            new_value=new_value or {},
            justification=justification or '',
            success=success,
            error_message=error_message or '',
            metadata=metadata or {},
            request_id=request_id
        )

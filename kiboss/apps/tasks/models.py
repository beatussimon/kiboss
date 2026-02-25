"""
Tasks App - Custom Internal Workflow System

This module handles:
- Task assignment for staff (Verifiers, Support, etc.)
- Generic task lifecycle (Pending -> Assigned -> Completed)
- Role-based task visibility
- Integration with other apps (verification, disputes, etc.)
"""

import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class TaskStatus(models.TextChoices):
    """Task status enumeration."""
    PENDING = 'PENDING', 'Pending'
    ASSIGNED = 'ASSIGNED', 'Assigned'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    REJECTED = 'REJECTED', 'Rejected'
    CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes Requested'
    CANCELLED = 'CANCELLED', 'Cancelled'


class TaskPriority(models.TextChoices):
    """Task priority level."""
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class TaskType(models.TextChoices):
    """Job task categories."""
    VEHICLE_VERIFICATION = 'VEHICLE_VERIFICATION', 'Vehicle Verification'
    IDENTITY_VERIFICATION = 'IDENTITY_VERIFICATION', 'Identity Verification'
    CORPORATE_RIDE_VERIFICATION = 'CORPORATE_RIDE_VERIFICATION', 'Corporate Ride Verification'
    CORPORATE_ASSET_VERIFICATION = 'CORPORATE_ASSET_VERIFICATION', 'Corporate Asset Verification'
    ASSET_AUDIT = 'ASSET_AUDIT', 'Asset Audit'
    DISPUTE_RESOLUTION = 'DISPUTE_RESOLUTION', 'Dispute Resolution'
    SUPPORT_TICKET = 'SUPPORT_TICKET', 'Support Ticket'
    CUSTOM_TASK = 'CUSTOM_TASK', 'Custom Task'


class StaffTask(models.Model):
    """
    Staff Task model for internal task assignment and tracking.
    This replaces/extends Django Admin for operational workflows.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Task identity
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=50, choices=TaskType.choices)
    
    # Status and priority
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING
    )
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM
    )
    
    # Assignment targets
    # Either a specific role can pick it up or it's assigned to an individual
    assigned_role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Role allowed to pick up this task (e.g. VERIFIER)"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_tasks'
    )
    
    # Linked resource (e.g., Asset being verified)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Task completion details
    reviewer_notes = models.TextField(blank=True)
    completion_date = models.DateTimeField(blank=True, null=True)
    
    # Scalability - allow attaching any JSON data to a task
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_tasks'
    )
    
    class Meta:
        db_table = 'staff_tasks'
        verbose_name = 'Staff Task'
        verbose_name_plural = 'Staff Tasks'
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['status', 'assigned_role']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['task_type']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.task_type}: {self.title} ({self.status})"

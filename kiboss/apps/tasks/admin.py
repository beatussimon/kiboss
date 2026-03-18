"""
Django Admin Configuration for Tasks App
"""

from django.contrib import admin
from .models import StaffTask, TaskStatus, TaskPriority, TaskType


@admin.register(StaffTask)
class StaffTaskAdmin(admin.ModelAdmin):
    """
    Admin configuration for StaffTask model.
    """
    
    list_display = [
        'id', 'title', 'task_type', 'assigned_to', 
        'status_badge', 'priority_badge', 'created_at'
    ]
    list_display_links = ['id', 'title']
    
    list_filter = [
        'status', 'priority', 'task_type', 
        'created_at'
    ]
    
    search_fields = [
        'title', 'description', 'assigned_to__email',
        'created_by__email'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Task Details', {
            'fields': ('id', 'title', 'description', 'task_type')
        }),
        ('Assignment', {
            'fields': ('assigned_role', 'assigned_to', 'created_by')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Linked Resource', {
            'fields': ('content_type', 'object_id')
        }),
        ('Completion', {
            'fields': ('reviewer_notes', 'completion_date')
        }),
        ('Metadata', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            TaskStatus.PENDING: '#ffc107',
            TaskStatus.ASSIGNED: '#17a2b8',
            TaskStatus.IN_PROGRESS: '#17a2b8',
            TaskStatus.COMPLETED: '#28a745',
            TaskStatus.REJECTED: '#dc3545',
            TaskStatus.CANCELLED: '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        from django.utils.html import format_html
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        """Display priority as color-coded badge."""
        priority_colors = {
            TaskPriority.LOW: '#6c757d',
            TaskPriority.MEDIUM: '#17a2b8',
            TaskPriority.HIGH: '#ffc107',
            TaskPriority.URGENT: '#dc3545',
        }
        color = priority_colors.get(obj.priority, '#6c757d')
        from django.utils.html import format_html
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected tasks as completed."""
        queryset.update(status=TaskStatus.COMPLETED)
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected tasks as cancelled."""
        queryset.update(status=TaskStatus.CANCELLED)
    mark_as_cancelled.short_description = "Mark as cancelled"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'assigned_to', 'created_by', 'content_type'
        )

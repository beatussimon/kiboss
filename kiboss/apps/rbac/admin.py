"""
Enhanced Django Admin Configuration for RBAC App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse

from .models import RolePermission, UserRole, AdminAction, Role, Permission


# =============================================================================
# CUSTOM ACTIONS
# =============================================================================

def export_to_csv(modeladmin, request, queryset):
    """Export selected objects to CSV format."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model.__name__}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    if queryset.exists():
        fields = queryset[0]._meta.get_fields()
        field_names = [f.name for f in fields]
        writer.writerow(field_names)
        
        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, field.name, '')
                if hasattr(value, '__str__'):
                    value = str(value)
                row.append(value)
            writer.writerow(row)
    
    return response


export_to_csv.short_description = "Export to CSV"


# =============================================================================
# ROLE PERMISSION ADMIN
# =============================================================================

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """
    Admin configuration for RolePermission model.
    """
    
    list_display = ['role', 'permission']
    list_filter = ['role']
    search_fields = ['role', 'permission']
    ordering = ['role', 'permission']
    list_per_page = 50
    
    actions = [export_to_csv]


# =============================================================================
# USER ROLE ADMIN
# =============================================================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserRole model.
    """
    
    readonly_fields = ['created_at']
    list_display = [
        'user', 'role', 'scope_type', 'scope_id',
        'expires_at', 'created_by'
    ]
    list_filter = ['role', 'scope_type', 'created_at']
    search_fields = ['user__email', 'scope_type']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('User Role', {
            'fields': ('user', 'role')
        }),
        ('Scope', {
            'fields': ('scope_type', 'scope_id')
        }),
        ('Expiry', {
            'fields': ('expires_at',)
        }),
        ('Created By', {
            'fields': ('created_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'user', 'created_by'
        )


# =============================================================================
# ADMIN ACTION ADMIN
# =============================================================================

@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    """
    Admin configuration for AdminAction model.
    """
    
    readonly_fields = ['created_at']
    list_display = [
        'admin', 'action_type', 'resource_type',
        'resource_id', 'justification_preview',
        'approved', 'created_at'
    ]
    list_filter = ['action_type', 'resource_type', 'approved', 'created_at']
    search_fields = ['action_type', 'resource_type', 'resource_id', 'justification']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Action Details', {
            'fields': ('admin', 'action_type', 'resource_type', 'resource_id')
        }),
        ('Justification', {
            'fields': ('justification',)
        }),
        ('Changes', {
            'fields': ('old_value', 'new_value'),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': ('approved', 'approval_notes'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv]
    
    def justification_preview(self, obj):
        """Show truncated justification."""
        if len(obj.justification) > 50:
            return obj.justification[:50] + '...'
        return obj.justification
    justification_preview.short_description = 'Justification'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('admin')


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_rbac_stats():
    """Get summary statistics for RBAC."""
    from django.db.models import Count
    
    stats = {
        'total_role_permissions': RolePermission.objects.count(),
        'total_user_roles': UserRole.objects.count(),
        'total_admin_actions': AdminAction.objects.count(),
        'pending_approvals': AdminAction.objects.filter(approved=False).count(),
        'by_role': dict(UserRole.objects.values('role').annotate(
            count=Count('id')
        ).values_list('role', 'count')),
    }
    return stats

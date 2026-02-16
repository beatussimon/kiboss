"""
Enhanced Django Admin Configuration for Audits App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse

from .models import AuditLog, AuditAction


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
# AUDIT LOG ADMIN
# =============================================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for AuditLog model.
    
    Read-only admin for viewing audit logs.
    """
    
    readonly_fields = [
        'id', 'actor', 'actor_ip', 'actor_user_agent',
        'action', 'resource_type', 'resource_id',
        'description', 'old_value', 'new_value',
        'justification', 'request_id', 'trace_id',
        'success', 'error_message', 'metadata', 'created_at'
    ]
    
    list_display = [
        'id', 'actor_preview', 'action_badge',
        'resource_type', 'resource_id_preview',
        'description_preview', 'success',
        'created_at'
    ]
    
    list_filter = [
        'action', 'resource_type', 'success',
        'created_at'
    ]
    
    search_fields = [
        'id', 'actor__email', 'action',
        'resource_type', 'resource_id', 'description',
        'error_message'
    ]
    
    ordering = ['-created_at']
    list_per_page = 50
    list_max_show_all = 2000
    
    fieldsets = (
        ('Actor', {
            'fields': ('id', 'actor', 'actor_ip', 'actor_user_agent')
        }),
        ('Action', {
            'fields': ('action', 'resource_type', 'resource_id', 'description')
        }),
        ('Changes', {
            'fields': ('old_value', 'new_value'),
            'classes': ('collapse',)
        }),
        ('Justification', {
            'fields': ('justification',),
            'classes': ('collapse',)
        }),
        ('Request Context', {
            'fields': ('request_id', 'trace_id'),
            'classes': ('collapse',)
        }),
        ('Result', {
            'fields': ('success', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
        }),
    )
    
    actions = [export_to_csv]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('actor')
    
    def actor_preview(self, obj):
        """Show actor email or IP."""
        if obj.actor:
            return obj.actor.email
        elif obj.actor_ip:
            return obj.actor_ip
        return 'System'
    actor_preview.short_description = 'Actor'
    actor_preview.admin_order_field = 'actor'
    
    def action_badge(self, obj):
        """Display action with color coding."""
        action_colors = {
            'LOGIN': '#28a745',
            'LOGOUT': '#6c757d',
            'LOGIN_FAILED': '#dc3545',
            'PASSWORD_CHANGE': '#ffc107',
            'TOKEN_REFRESH': '#17a2b8',
            'USER_BANNED': '#dc3545',
            'USER_UNBANNED': '#28a745',
            'USER_VERIFIED': '#28a745',
            'ASSET_VERIFIED': '#28a745',
            'ASSET_REJECTED': '#dc3545',
            'BOOKING_OVERRIDE': '#fd7e14',
            'CONTRACT_OVERRIDE': '#fd7e14',
            'PAYMENT_OVERRIDE': '#fd7e14',
            'DISPUTE_RESOLVED': '#28a745',
            'RATING_MODERATED': '#6f42c1',
        }
        color = action_colors.get(obj.action, '#6c757d')
        from django.utils.html import format_html
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    action_badge.admin_order_field = 'action'
    
    def resource_id_preview(self, obj):
        """Show truncated resource ID."""
        if obj.resource_id:
            return str(obj.resource_id)[:8]
        return ''
    resource_id_preview.short_description = 'Resource ID'
    
    def description_preview(self, obj):
        """Show truncated description."""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_preview.short_description = 'Description'


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_audit_stats():
    """Get summary statistics for audits."""
    from django.db.models import Count
    from .models import AuditLog
    
    stats = {
        'total_audit_logs': AuditLog.objects.count(),
        'today_logs': AuditLog.objects.filter(
            created_at__date=datetime.now().date()
        ).count(),
        'failed_actions': AuditLog.objects.filter(success=False).count(),
        'admin_actions': AuditLog.objects.filter(
            action__in=[
                'USER_BANNED', 'USER_UNBANNED', 'USER_VERIFIED',
                'ASSET_VERIFIED', 'ASSET_REJECTED', 'BOOKING_OVERRIDE',
                'CONTRACT_OVERRIDE', 'PAYMENT_OVERRIDE', 'DISPUTE_RESOLVED',
                'RATING_MODERATED'
            ]
        ).count(),
        'by_action': dict(AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).values_list('action', 'count')),
    }
    return stats

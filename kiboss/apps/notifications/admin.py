"""
Enhanced Django Admin Configuration for Notifications App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Notification, NotificationPreference, NotificationStatus, NotificationCategory


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


def mark_as_read(modeladmin, request, queryset):
    """Mark selected notifications as read."""
    for notification in queryset:
        notification.mark_read()
mark_as_read.short_description = "Mark as read"


def resend_notifications(modeladmin, request, queryset):
    """Resend selected pending/failed notifications."""
    queryset.filter(status__in=[NotificationStatus.PENDING, NotificationStatus.FAILED]).update(
        status=NotificationStatus.PENDING,
        retry_count=0,
        failure_reason=''
    )
resend_notifications.short_description = "Resend notifications"


# =============================================================================
# NOTIFICATION ADMIN
# =============================================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Notification model.
    """
    
    readonly_fields = [
        'id', 'created_at', 'updated_at', 
        'sent_at', 'delivered_at', 'read_at'
    ]
    list_display = [
        'id', 'user', 'category_badge', 'title_preview',
        'status_badge', 'priority', 'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'category', 'priority',
        'created_at', 'sent_at'
    ]
    
    search_fields = [
        'id', 'user__email', 'title', 'message',
        'notification_type'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('id', 'user', 'category', 'notification_type')
        }),
        ('Content', {
            'fields': ('title', 'message', 'action_url')
        }),
        ('Status', {
            'fields': ('status', 'channels')
        }),
        ('Delivery', {
            'fields': ('sent_at', 'delivered_at', 'read_at')
        }),
        ('Failure', {
            'fields': ('failure_reason', 'retry_count'),
            'classes': ('collapse',)
        }),
        ('Context', {
            'fields': ('booking', 'ride'),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('priority', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv, mark_as_read, resend_notifications]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'user', 'booking', 'ride'
        )
    
    def title_preview(self, obj):
        """Show truncated title."""
        if len(obj.title) > 40:
            return obj.title[:40] + '...'
        return obj.title
    title_preview.short_description = 'Title'
    
    def category_badge(self, obj):
        """Display category as color-coded badge."""
        category_colors = {
            'BOOKING': '#28a745',
            'RIDE': '#007bff',
            'PAYMENT': '#17a2b8',
            'CONTRACT': '#6f42c1',
            'MESSAGE': '#ffc107',
            'RATING': '#fd7e14',
            'SYSTEM': '#6c757d',
            'MARKETING': '#e83e8c',
        }
        color = category_colors.get(obj.category, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_category_display()
        )
    category_badge.short_description = 'Category'
    category_badge.admin_order_field = 'category'
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'PENDING': '#ffc107',
            'SENT': '#17a2b8',
            'DELIVERED': '#28a745',
            'READ': '#28a745',
            'FAILED': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """
    Admin configuration for NotificationPreference model.
    """
    
    list_display = [
        'user', 'email_enabled', 'push_enabled', 
        'sms_enabled', 'quiet_hours_enabled'
    ]
    list_filter = [
        'email_enabled', 'push_enabled', 'sms_enabled',
        'quiet_hours_enabled', 'created_at'
    ]
    search_fields = ['user__email']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Channel Preferences', {
            'fields': ('email_enabled', 'push_enabled', 'sms_enabled')
        }),
        ('Category Preferences', {
            'fields': ('categories',)
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv]


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_notification_stats():
    """Get summary statistics for notifications."""
    from django.db.models import Count
    from .models import Notification
    
    stats = {
        'total_notifications': Notification.objects.count(),
        'pending_notifications': Notification.objects.filter(
            status=NotificationStatus.PENDING
        ).count(),
        'sent_notifications': Notification.objects.filter(
            status=NotificationStatus.SENT
        ).count(),
        'delivered_notifications': Notification.objects.filter(
            status=NotificationStatus.DELIVERED
        ).count(),
        'read_notifications': Notification.objects.filter(
            status=NotificationStatus.READ
        ).count(),
        'failed_notifications': Notification.objects.filter(
            status=NotificationStatus.FAILED
        ).count(),
        'by_category': dict(Notification.objects.values('category').annotate(
            count=Count('id')
        ).values_list('category', 'count')),
    }
    return stats

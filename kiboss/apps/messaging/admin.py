"""
Enhanced Django Admin Configuration for Messaging App

This module provides a fully-featured admin interface for messaging management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for messages
- Batch operations and bulk actions
- CSV export functionality
- Role-based access control
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Thread, Message, MessageAttachment, MessageRateLimit, ThreadStatus, ThreadType


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


def open_threads(modeladmin, request, queryset):
    """Open selected threads."""
    queryset.update(status=ThreadStatus.OPEN)
open_threads.short_description = "Open threads"


def close_threads(modeladmin, request, queryset):
    """Close selected threads."""
    queryset.update(status=ThreadStatus.CLOSED)
close_threads.short_description = "Close threads"


def archive_threads(modeladmin, request, queryset):
    """Archive selected threads."""
    queryset.update(status=ThreadStatus.ARCHIVED)
archive_threads.short_description = "Archive threads"


def flag_threads(modeladmin, request, queryset):
    """Flag selected threads for moderation."""
    queryset.update(is_flagged=True)
flag_threads.short_description = "Flag threads"


def unflag_threads(modeladmin, request, queryset):
    """Unflag selected threads."""
    queryset.update(is_flagged=False, flagged_reason='')
unflag_threads.short_description = "Unflag threads"


# =============================================================================
# MESSAGE INLINE
# =============================================================================

class MessageInline(admin.TabularInline):
    """
    Inline admin for Message - tabular display.
    """
    model = Message
    extra = 0
    min_num = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['sender', 'content', 'content_type', 'status', 'created_at']
    show_change_link = True


class MessageAttachmentInline(admin.TabularInline):
    """
    Inline admin for MessageAttachment - tabular display.
    """
    model = MessageAttachment
    extra = 0
    min_num = 0
    readonly_fields = ['created_at']
    fields = ['file', 'file_type', 'file_name', 'file_size', 'is_safe', 'created_at']
    show_change_link = True


# =============================================================================
# THREAD ADMIN
# =============================================================================

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Thread model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at', 'message_count']
    list_display = [
        'id', 'thread_type_badge', 'status_badge', 'subject',
        'participant_count', 'is_flagged', 'message_count',
        'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'thread_type', 'status', 'is_flagged', 
        'created_at', 'updated_at'
    ]
    
    search_fields = [
        'id', 'subject', 'participants__email',
        'booking__id', 'ride__id'
    ]
    
    ordering = ['-updated_at']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [MessageInline]  # MessageAttachment is linked to Message, not Thread
    
    fieldsets = (
        ('Thread Details', {
            'fields': ('id', 'thread_type', 'status', 'subject')
        }),
        ('Participants', {
            'fields': ('participants',)
        }),
        ('Context', {
            'fields': ('booking', 'ride')
        }),
        ('Moderation', {
            'fields': ('is_flagged', 'flagged_reason', 'moderated_by')
        }),
        ('Locking', {
            'fields': ('auto_lock_after_completion', 'locked_at', 'locked_by'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('message_count',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        export_to_csv, open_threads, close_threads, 
        archive_threads, flag_threads, unflag_threads
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch_related."""
        return super().get_queryset(request).prefetch_related('participants')
    
    def participant_count(self, obj):
        """Display number of participants."""
        return obj.participants.count()
    participant_count.short_description = 'Participants'
    
    def thread_type_badge(self, obj):
        """Display thread type as color-coded badge."""
        type_colors = {
            'INQUIRY': '#17a2b8',
            'BOOKING': '#28a745',
            'RIDE': '#007bff',
            'DISPUTE': '#dc3545',
            'DIRECT': '#6c757d',
            'SUPPORT': '#6f42c1',
        }
        color = type_colors.get(obj.thread_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_thread_type_display()
        )
    thread_type_badge.short_description = 'Type'
    thread_type_badge.admin_order_field = 'thread_type'
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'OPEN': '#28a745',
            'LOCKED': '#ffc107',
            'CLOSED': '#6c757d',
            'ARCHIVED': '#343a40',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Message model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_display = [
        'id', 'thread', 'sender', 'content_preview',
        'status', 'is_deleted', 'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'content_type', 'is_deleted',
        'created_at'
    ]
    
    search_fields = [
        'id', 'thread__id', 'sender__email', 'content'
    ]
    
    ordering = ['-created_at']
    list_per_page = 50
    list_max_show_all = 1000
    
    fieldsets = (
        ('Message Details', {
            'fields': ('id', 'thread', 'sender', 'content', 'content_type')
        }),
        ('Status', {
            'fields': ('status', 'read_at')
        }),
        ('Deletion', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv]
    
    def content_preview(self, obj):
        """Show truncated content."""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = 'Content'


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    """Admin configuration for MessageAttachment model."""
    
    list_display = ['message', 'file_type', 'file_name', 'file_size', 'is_safe', 'created_at']
    list_filter = ['file_type', 'is_safe', 'created_at']
    search_fields = ['message__thread__id', 'file_name']
    ordering = ['-created_at']
    list_per_page = 50


@admin.register(MessageRateLimit)
class MessageRateLimitAdmin(admin.ModelAdmin):
    """Admin configuration for MessageRateLimit model."""
    
    list_display = ['user', 'message_count', 'window_start']
    search_fields = ['user__email']
    ordering = ['-window_start']
    list_per_page = 50


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_messaging_stats():
    """Get summary statistics for messaging."""
    from django.db.models import Count
    
    stats = {
        'total_threads': Thread.objects.count(),
        'open_threads': Thread.objects.filter(status=ThreadStatus.OPEN).count(),
        'flagged_threads': Thread.objects.filter(is_flagged=True).count(),
        'total_messages': Message.objects.count(),
        'deleted_messages': Message.objects.filter(is_deleted=True).count(),
        'by_type': dict(Thread.objects.values('thread_type').annotate(
            count=Count('id')
        ).values_list('thread_type', 'count')),
    }
    return stats

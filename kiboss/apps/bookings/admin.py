"""
Enhanced Django Admin Configuration for Bookings App

This module provides a fully-featured admin interface for booking management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for timeline events
- Batch operations and bulk actions
- CSV export functionality
- Role-based access control
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Booking, BookingStatusTransition, BookingTimeline, BookingLock, BookingStatus


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


def confirm_bookings(modeladmin, request, queryset):
    """Confirm selected pending bookings."""
    for booking in queryset.filter(status=BookingStatus.PENDING):
        try:
            booking.transition_to(
                BookingStatus.CONFIRMED, 
                actor_type='ADMIN',
                actor_id=request.user.id,
                reason='Admin confirmation'
            )
        except ValueError:
            pass
confirm_bookings.short_description = "Confirm bookings"


def cancel_bookings(modeladmin, request, queryset):
    """Cancel selected bookings."""
    for booking in queryset.filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED]):
        try:
            booking.transition_to(
                BookingStatus.CANCELLED,
                actor_type='ADMIN',
                actor_id=request.user.id,
                reason='Admin cancellation'
            )
        except ValueError:
            pass
cancel_bookings.short_description = "Cancel bookings"


def activate_bookings(modeladmin, request, queryset):
    """Activate selected confirmed bookings."""
    for booking in queryset.filter(status=BookingStatus.CONFIRMED):
        try:
            booking.transition_to(
                BookingStatus.ACTIVE,
                actor_type='ADMIN',
                actor_id=request.user.id,
                reason='Admin activation'
            )
        except ValueError:
            pass
activate_bookings.short_description = "Activate bookings"


def complete_bookings(modeladmin, request, queryset):
    """Complete selected active bookings."""
    for booking in queryset.filter(status=BookingStatus.ACTIVE):
        try:
            booking.transition_to(
                BookingStatus.COMPLETED,
                actor_type='ADMIN',
                actor_id=request.user.id,
                reason='Admin completion'
            )
        except ValueError:
            pass
complete_bookings.short_description = "Complete bookings"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class BookingStatusTransitionInline(admin.TabularInline):
    """
    Inline admin for BookingStatusTransition - tabular display.
    """
    model = BookingStatusTransition
    extra = 0
    min_num = 0
    readonly_fields = ['created_at']
    fields = ['from_status', 'to_status', 'actor_type', 'actor_id', 
              'reason', 'justification', 'created_at']
    ordering = ['-created_at']


class BookingTimelineInline(admin.TabularInline):
    """
    Inline admin for BookingTimeline - tabular display.
    """
    model = BookingTimeline
    extra = 0
    min_num = 0
    readonly_fields = ['created_at']
    fields = ['event_type', 'description', 'actor_type', 'actor_id', 'data', 'created_at']
    ordering = ['created_at']


# =============================================================================
# BOOKING ADMIN
# =============================================================================

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Booking model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at', 'cancelled_at', 'completed_at']
    list_display = [
        'id', 'renter', 'asset', 'status_badge',
        'start_time', 'end_time', 'quantity',
        'total_price', 'currency', 'is_late',
        'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'currency', 'is_late',
        'created_at', 'start_time', 'end_time'
    ]
    
    search_fields = [
        'id', 'renter__email', 'asset__name',
        'renter_notes', 'owner_notes'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [BookingStatusTransitionInline, BookingTimelineInline]
    
    fieldsets = (
        ('Booking Details', {
            'fields': ('id', 'renter', 'asset', 'status')
        }),
        ('Time', {
            'fields': ('start_time', 'end_time', 'timezone')
        }),
        ('Quantity & Pricing', {
            'fields': ('quantity', 'unit_price', 'subtotal', 
                      'service_fee', 'taxes', 'total_price', 'currency')
        }),
        ('Related Objects', {
            'fields': ('contract', 'payment')
        }),
        ('Grace Periods', {
            'fields': ('grace_period_minutes', 'buffer_minutes')
        }),
        ('Late Fees', {
            'fields': ('late_fee_per_unit', 'late_fee_max')
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancelled_by', 'cancellation_reason', 'cancellation_fee'),
            'classes': ('collapse',)
        }),
        ('Completion', {
            'fields': ('completed_at', 'actual_return_time'),
            'classes': ('collapse',)
        }),
        ('Late Return', {
            'fields': ('is_late', 'late_minutes', 'late_fee_charged'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('renter_notes', 'owner_notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        export_to_csv, confirm_bookings, cancel_bookings,
        activate_bookings, complete_bookings
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'renter', 'asset', 'contract', 'payment'
        )
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'PENDING': '#ffc107',
            'CONFIRMED': '#17a2b8',
            'ACTIVE': '#007bff',
            'COMPLETED': '#28a745',
            'CANCELLED': '#dc3545',
            'EXPIRED': '#6c757d',
            'DISPUTED': '#fd7e14',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(BookingStatusTransition)
class BookingStatusTransitionAdmin(admin.ModelAdmin):
    """Admin configuration for BookingStatusTransition model."""
    
    readonly_fields = ['created_at']
    list_display = [
        'booking', 'from_status', 'to_status',
        'actor_type', 'actor_id', 'reason', 'created_at'
    ]
    list_filter = ['actor_type', 'from_status', 'to_status', 'created_at']
    search_fields = ['booking__id', 'reason']
    ordering = ['-created_at']
    list_per_page = 50


@admin.register(BookingTimeline)
class BookingTimelineAdmin(admin.ModelAdmin):
    """Admin configuration for BookingTimeline model."""
    
    readonly_fields = ['created_at']
    list_display = [
        'booking', 'event_type', 'description_preview',
        'actor_type', 'created_at'
    ]
    list_filter = ['event_type', 'actor_type', 'created_at']
    search_fields = ['booking__id', 'description']
    ordering = ['-created_at']
    list_per_page = 50
    
    def description_preview(self, obj):
        """Show truncated description."""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_preview.short_description = 'Description'


@admin.register(BookingLock)
class BookingLockAdmin(admin.ModelAdmin):
    """Admin configuration for BookingLock model."""
    
    list_display = [
        'lock_type', 'resource_type', 'resource_id',
        'owner_id', 'owner_process', 'expires_at'
    ]
    list_filter = ['lock_type', 'resource_type']
    search_fields = ['resource_id', 'owner_id']
    ordering = ['-expires_at']
    list_per_page = 50


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_booking_stats():
    """Get summary statistics for bookings."""
    from django.db.models import Sum, Count
    from .models import Booking
    
    stats = {
        'total_bookings': Booking.objects.count(),
        'pending_bookings': Booking.objects.filter(status=BookingStatus.PENDING).count(),
        'confirmed_bookings': Booking.objects.filter(status=BookingStatus.CONFIRMED).count(),
        'active_bookings': Booking.objects.filter(status=BookingStatus.ACTIVE).count(),
        'completed_bookings': Booking.objects.filter(status=BookingStatus.COMPLETED).count(),
        'cancelled_bookings': Booking.objects.filter(status=BookingStatus.CANCELLED).count(),
        'disputed_bookings': Booking.objects.filter(status=BookingStatus.DISPUTED).count(),
        'late_returns': Booking.objects.filter(is_late=True).count(),
        'total_revenue': Booking.objects.filter(
            status__in=[BookingStatus.COMPLETED, BookingStatus.ACTIVE]
        ).aggregate(Sum('total_price'))['total_price__sum'] or 0,
    }
    return stats

"""
Enhanced Django Admin Configuration for Rides App

This module provides a fully-featured admin interface for ride management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for related models (stops, bookings)
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

from .models import Ride, RideStop, SeatBooking, RideSchedule, RideStatus, SeatBookingStatus


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


def open_rides(modeladmin, request, queryset):
    """Open selected rides for booking."""
    queryset.update(status=RideStatus.OPEN)
open_rides.short_description = "Open rides for booking"


def cancel_rides(modeladmin, request, queryset):
    """Cancel selected rides."""
    queryset.update(status=RideStatus.CANCELLED)
cancel_rides.short_description = "Cancel selected rides"


def complete_rides(modeladmin, request, queryset):
    """Mark selected rides as completed."""
    queryset.update(status=RideStatus.COMPLETED)
complete_rides.short_description = "Mark as completed"


def confirm_seat_bookings(modeladmin, request, queryset):
    """Confirm selected seat bookings."""
    queryset.filter(status=SeatBookingStatus.RESERVED).update(
        status=SeatBookingStatus.CONFIRMED
    )
confirm_seat_bookings.short_description = "Confirm seat bookings"


def cancel_seat_bookings(modeladmin, request, queryset):
    """Cancel selected seat bookings."""
    queryset.update(status=SeatBookingStatus.CANCELLED)
cancel_seat_bookings.short_description = "Cancel seat bookings"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class RideStopInline(admin.TabularInline):
    """
    Inline admin for RideStop - tabular display with ordering.
    """
    model = RideStop
    extra = 0
    min_num = 0
    fields = ['stop_type', 'name', 'address', 'latitude', 'longitude', 
              'estimated_arrival', 'departure_time', 'stop_order', 'notes']
    readonly_fields = []
    
    def get_queryset(self, request):
        """Order stops by stop_order."""
        return super().get_queryset(request).order_by('stop_order')


class SeatBookingInline(admin.TabularInline):
    """
    Inline admin for SeatBooking - tabular display.
    """
    model = SeatBooking
    extra = 0
    min_num = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['passenger', 'seat_number', 'status', 'pickup_stop', 
              'dropoff_stop', 'price', 'checked_in_at', 'boarded_at']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'passenger', 'pickup_stop', 'dropoff_stop'
        ).order_by('seat_number')


# =============================================================================
# RIDE ADMIN
# =============================================================================

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Ride model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_display = [
        'id', 'route_name', 'driver', 'status_badge', 
        'origin', 'destination', 'departure_time',
        'available_seats_display', 'confirmed_seats', 
        'seat_price', 'created_at'
    ]
    list_display_links = ['id', 'route_name']
    
    list_filter = [
        'status', 'is_recurring', 'created_at', 
        'departure_time', 'vehicle_color'
    ]
    
    search_fields = [
        'id', 'route_name', 'origin', 'destination',
        'driver__email', 'vehicle_license_plate'
    ]
    
    ordering = ['-departure_time']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [RideStopInline, SeatBookingInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'driver', 'vehicle_asset', 'status')
        }),
        ('Route Details', {
            'fields': ('route_name', 'origin', 'destination', 'waypoints')
        }),
        ('Schedule', {
            'fields': ('departure_time', 'estimated_arrival', 'actual_arrival',
                      'is_recurring', 'recurring_pattern')
        }),
        ('Capacity & Pricing', {
            'fields': ('total_seats', 'reserved_seats', 'confirmed_seats',
                      'seat_price', 'currency')
        }),
        ('Vehicle Details', {
            'fields': ('vehicle_description', 'vehicle_color', 
                      'vehicle_license_plate', 'driver_notes')
        }),
        ('Policies', {
            'fields': ('cancellation_cutoff_minutes', 'no_show_cutoff_minutes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        export_to_csv, open_rides, cancel_rides, complete_rides
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'driver', 'vehicle_asset'
        ).prefetch_related('stops', 'seat_bookings')
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'SCHEDULED': '#17a2b8',
            'OPEN': '#28a745',
            'FULL': '#ffc107',
            'DEPARTED': '#6c757d',
            'IN_TRANSIT': '#007bff',
            'COMPLETED': '#28a745',
            'CANCELLED': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def available_seats_display(self, obj):
        """Display available seats."""
        available = obj.get_available_seats()
        if available == 0:
            color = '#dc3545'
        elif available <= 2:
            color = '#ffc107'
        else:
            color = '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{}</span>',
            color, available, obj.total_seats
        )
    available_seats_display.short_description = 'Available Seats'
    available_seats_display.admin_order_field = 'total_seats'


@admin.register(RideStop)
class RideStopAdmin(admin.ModelAdmin):
    """Admin configuration for RideStop model."""
    
    list_display = ['ride', 'stop_type', 'name', 'stop_order', 'estimated_arrival', 'departure_time']
    list_filter = ['stop_type']
    search_fields = ['ride__route_name', 'ride__origin', 'ride__destination', 'name']
    ordering = ['ride', 'stop_order']
    list_per_page = 50


@admin.register(SeatBooking)
class SeatBookingAdmin(admin.ModelAdmin):
    """Admin configuration for SeatBooking model."""
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_display = [
        'id', 'ride', 'passenger', 'seat_number', 
        'status_badge', 'pickup_stop', 'dropoff_stop',
        'price', 'boarded_at', 'created_at'
    ]
    list_display_links = ['id', 'passenger']
    
    list_filter = ['status', 'created_at', 'boarded_at']
    search_fields = ['ride__route_name', 'passenger__email', 'id']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Booking Details', {
            'fields': ('id', 'ride', 'passenger', 'seat_number', 'status')
        }),
        ('Route', {
            'fields': ('pickup_stop', 'dropoff_stop')
        }),
        ('Pricing', {
            'fields': ('price', 'currency')
        }),
        ('Passenger Details', {
            'fields': ('passenger_notes', 'luggage_count')
        }),
        ('Check-in', {
            'fields': ('checked_in_at', 'boarded_at')
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('No-Show', {
            'fields': ('marked_no_show_at', 'no_show_penalty_applied'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv, confirm_seat_bookings, cancel_seat_bookings]
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'RESERVED': '#ffc107',
            'CONFIRMED': '#28a745',
            'CANCELLED': '#dc3545',
            'NO_SHOW': '#6c757d',
            'BOARDED': '#17a2b8',
            'COMPLETED': '#28a745',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'ride', 'passenger', 'pickup_stop', 'dropoff_stop'
        )


@admin.register(RideSchedule)
class RideScheduleAdmin(admin.ModelAdmin):
    """Admin configuration for RideSchedule model."""
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_display = [
        'id', 'name', 'driver', 'schedule_type', 'origin', 
        'destination', 'departure_time', 'total_seats',
        'seat_price', 'is_active'
    ]
    list_display_links = ['id', 'name']
    
    list_filter = ['schedule_type', 'is_active', 'created_at']
    search_fields = ['name', 'driver__email', 'origin', 'destination']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Schedule Details', {
            'fields': ('id', 'driver', 'name', 'schedule_type')
        }),
        ('Route', {
            'fields': ('origin', 'destination', 'waypoints')
        }),
        ('Timing', {
            'fields': ('departure_time', 'estimated_duration_minutes', 'recurrence_days')
        }),
        ('Capacity & Pricing', {
            'fields': ('total_seats', 'seat_price', 'currency')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'is_active')
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

def get_ride_stats():
    """Get summary statistics for rides."""
    from django.db.models import Count, Sum
    from .models import Ride, SeatBooking
    
    stats = {
        'total_rides': Ride.objects.count(),
        'scheduled_rides': Ride.objects.filter(status=RideStatus.SCHEDULED).count(),
        'open_rides': Ride.objects.filter(status=RideStatus.OPEN).count(),
        'in_transit_rides': Ride.objects.filter(status=RideStatus.IN_TRANSIT).count(),
        'completed_rides': Ride.objects.filter(status=RideStatus.COMPLETED).count(),
        'cancelled_rides': Ride.objects.filter(status=RideStatus.CANCELLED).count(),
        'total_revenue': SeatBooking.objects.filter(
            status=SeatBookingStatus.CONFIRMED
        ).aggregate(Sum('price'))['price__sum'] or 0,
    }
    return stats

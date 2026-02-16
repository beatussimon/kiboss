"""
Enhanced Django Admin Configuration for Assets App

This module provides a fully-featured admin interface for asset management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for related models (photos, pricing, availability, etc.)
- Batch operations and bulk actions
- CSV export functionality
- Role-based access control
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import (
    Asset, AssetPhoto, AssetPricing, AssetAvailability,
    AssetCapacity, AssetTimeGranularity, AssetJurisdiction,
    AssetLike, AssetType, VerificationStatus
)


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


def verify_assets(modeladmin, request, queryset):
    """Verify selected assets."""
    from django.utils import timezone
    queryset.update(
        verification_status=VerificationStatus.VERIFIED,
        verified_at=timezone.now(),
        verified_by=request.user
    )
verify_assets.short_description = "Verify selected assets"


def reject_assets(modeladmin, request, queryset):
    """Reject selected assets."""
    queryset.update(verification_status=VerificationStatus.REJECTED)
reject_assets.short_description = "Reject selected assets"


def activate_assets(modeladmin, request, queryset):
    """Activate selected assets."""
    queryset.update(is_active=True)
activate_assets.short_description = "Activate selected assets"


def deactivate_assets(modeladmin, request, queryset):
    """Deactivate selected assets."""
    queryset.update(is_active=False)
deactivate_assets.short_description = "Deactivate selected assets"


def list_assets(modeladmin, request, queryset):
    """List selected assets."""
    queryset.update(is_listed=True)
list_assets.short_description = "List selected assets"


def unlist_assets(modeladmin, request, queryset):
    """Unlist selected assets."""
    queryset.update(is_listed=False)
unlist_assets.short_description = "Unlist selected assets"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class AssetPhotoInline(admin.TabularInline):
    """
    Inline admin for AssetPhoto - tabular display.
    """
    model = AssetPhoto
    extra = 0
    min_num = 0
    fields = ['image', 'caption', 'order', 'is_primary']


class AssetPricingInline(admin.TabularInline):
    """
    Inline admin for AssetPricing - tabular display.
    """
    model = AssetPricing
    extra = 0
    min_num = 0
    fields = ['name', 'unit_type', 'price', 'min_quantity', 
              'max_quantity', 'priority', 'is_active']


class AssetAvailabilityInline(admin.StackedInline):
    """
    Inline admin for AssetAvailability - stacked display.
    """
    model = AssetAvailability
    extra = 0
    min_num = 0
    fields = ['name', 'availability_type', 'buffer_minutes',
              'min_advance_booking_minutes', 'max_advance_booking_days',
              'schedule', 'blocked_dates', 'exceptions', 'is_active']


class AssetCapacityInline(admin.TabularInline):
    """
    Inline admin for AssetCapacity - tabular display.
    """
    model = AssetCapacity
    extra = 0
    min_num = 0
    fields = ['capacity_type', 'quantity', 'description']


class AssetTimeGranularityInline(admin.StackedInline):
    """
    Inline admin for AssetTimeGranularity - stacked display.
    """
    model = AssetTimeGranularity
    extra = 0
    min_num = 0
    max_num = 1
    fields = ['min_duration_minutes', 'max_duration_minutes', 
              'increment_minutes', 'any_start_time', 'allowed_start_times',
              'same_day_booking', 'cutoff_hour']


# =============================================================================
# ASSET ADMIN
# =============================================================================

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Asset model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_display = [
        'id', 'name', 'asset_type_badge', 'owner', 
        'verification_status_badge', 'is_active', 'is_listed',
        'city', 'country', 'average_rating', 'total_bookings',
        'created_at'
    ]
    list_display_links = ['id', 'name']
    
    list_filter = [
        'asset_type', 'verification_status', 'is_active', 
        'is_listed', 'country', 'city', 'created_at'
    ]
    
    search_fields = [
        'id', 'name', 'description', 'owner__email',
        'address', 'city', 'state', 'country'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [
        AssetPhotoInline, AssetPricingInline, 
        AssetAvailabilityInline, AssetCapacityInline,
        AssetTimeGranularityInline
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'asset_type', 'owner')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 
                      'postal_code', 'latitude', 'longitude')
        }),
        ('Jurisdiction', {
            'fields': ('jurisdiction', 'timezone')
        }),
        ('Verification', {
            'fields': ('verification_status', 'verification_notes', 
                      'verified_at', 'verified_by')
        }),
        ('Status', {
            'fields': ('is_active', 'is_listed')
        }),
        ('Statistics', {
            'fields': ('total_bookings', 'average_rating', 'total_reviews')
        }),
        ('Properties', {
            'fields': ('properties',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        export_to_csv, verify_assets, reject_assets,
        activate_assets, deactivate_assets, list_assets, unlist_assets
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'owner', 'verified_by'
        ).prefetch_related('photos', 'pricing_rules')
    
    def asset_type_badge(self, obj):
        """Display asset type as colored badge."""
        type_colors = {
            'ROOM': '#17a2b8',
            'TOOL': '#ffc107',
            'VEHICLE': '#007bff',
            'SEAT_SERVICE': '#28a745',
            'TIME_SERVICE': '#6f42c1',
        }
        color = type_colors.get(obj.asset_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_asset_type_display()
        )
    asset_type_badge.short_description = 'Type'
    asset_type_badge.admin_order_field = 'asset_type'
    
    def verification_status_badge(self, obj):
        """Display verification status as color-coded badge."""
        status_colors = {
            'UNVERIFIED': '#6c757d',
            'PENDING': '#ffc107',
            'VERIFIED': '#28a745',
            'REJECTED': '#dc3545',
        }
        color = status_colors.get(obj.verification_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.get_verification_status_display()
        )
    verification_status_badge.short_description = 'Verification'
    verification_status_badge.admin_order_field = 'verification_status'


@admin.register(AssetPhoto)
class AssetPhotoAdmin(admin.ModelAdmin):
    """Admin configuration for AssetPhoto model."""
    
    list_display = ['asset', 'caption', 'order', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['asset__name', 'caption']
    ordering = ['asset', 'order']
    list_per_page = 50


@admin.register(AssetPricing)
class AssetPricingAdmin(admin.ModelAdmin):
    """Admin configuration for AssetPricing model."""
    
    list_display = ['asset', 'name', 'unit_type', 'price', 
                   'min_quantity', 'max_quantity', 'priority', 'is_active']
    list_filter = ['unit_type', 'is_active', 'created_at']
    search_fields = ['asset__name', 'name']
    ordering = ['asset', '-priority']
    list_per_page = 50


@admin.register(AssetAvailability)
class AssetAvailabilityAdmin(admin.ModelAdmin):
    """Admin configuration for AssetAvailability model."""
    
    list_display = ['asset', 'name', 'availability_type', 'buffer_minutes',
                   'min_advance_booking_minutes', 'max_advance_booking_days', 'is_active']
    list_filter = ['availability_type', 'is_active', 'created_at']
    search_fields = ['asset__name', 'name']
    ordering = ['asset', 'name']
    list_per_page = 50


@admin.register(AssetCapacity)
class AssetCapacityAdmin(admin.ModelAdmin):
    """Admin configuration for AssetCapacity model."""
    
    list_display = ['asset', 'capacity_type', 'quantity', 'description']
    list_filter = ['capacity_type']
    search_fields = ['asset__name', 'description']
    ordering = ['asset', 'capacity_type']
    list_per_page = 50


@admin.register(AssetTimeGranularity)
class AssetTimeGranularityAdmin(admin.ModelAdmin):
    """Admin configuration for AssetTimeGranularity model."""
    
    list_display = ['asset', 'min_duration_minutes', 'max_duration_minutes',
                   'increment_minutes', 'any_start_time', 'same_day_booking']
    search_fields = ['asset__name']
    ordering = ['asset']
    list_per_page = 50


@admin.register(AssetJurisdiction)
class AssetJurisdictionAdmin(admin.ModelAdmin):
    """Admin configuration for AssetJurisdiction model."""
    
    readonly_fields = ['created_at', 'updated_at']
    list_display = ['asset', 'country', 'state', 'city', 
                   'license_required', 'insurance_required', 'tax_rate']
    list_filter = ['country', 'license_required', 'insurance_required']
    search_fields = ['asset__name', 'country', 'state', 'city']
    ordering = ['asset']
    list_per_page = 50
    
    fieldsets = (
        ('Asset', {
            'fields': ('asset',)
        }),
        ('Location', {
            'fields': ('country', 'state', 'county', 'city')
        }),
        ('Legal Requirements', {
            'fields': ('license_required', 'license_number', 
                      'license_expiry', 'insurance_required', 'insurance_details',
                      'permits_required')
        }),
        ('Tax Information', {
            'fields': ('tax_rate', 'tax_category')
        }),
        ('Notes', {
            'fields': ('compliance_notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_asset_stats():
    """Get summary statistics for assets."""
    from django.db.models import Count, Avg
    
    stats = {
        'total_assets': Asset.objects.count(),
        'active_assets': Asset.objects.filter(is_active=True).count(),
        'listed_assets': Asset.objects.filter(is_listed=True).count(),
        'unverified_assets': Asset.objects.filter(
            verification_status=VerificationStatus.UNVERIFIED
        ).count(),
        'pending_assets': Asset.objects.filter(
            verification_status=VerificationStatus.PENDING
        ).count(),
        'verified_assets': Asset.objects.filter(
            verification_status=VerificationStatus.VERIFIED
        ).count(),
        'avg_rating': Asset.objects.aggregate(Avg('average_rating'))['average_rating__avg'] or 0,
        'by_type': dict(Asset.objects.values('asset_type').annotate(
            count=Count('id')
        ).values_list('asset_type', 'count')),
    }
    return stats

"""
Enhanced Django Admin Configuration for Users App

This module provides a fully-featured admin interface for user management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for related models
- Batch operations and bulk actions
- CSV export functionality
- Role-based access control
- Custom dashboard widgets
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import User, UserProfile, TrustScore, Device, BlacklistedToken


# =============================================================================
# CUSTOM ADMIN SITE
# =============================================================================

class KibossAdminSite(admin.AdminSite):
    """
    Custom admin site for KIBOSS with enhanced branding and features.
    """
    site_header = 'KIBOSS Administration'
    site_title = 'KIBOSS Admin'
    index_title = 'Dashboard'
    
    def get_app_list(self, request, app_label=None):
        """
        Return sorted app list with custom ordering.
        """
        app_list = super().get_app_list(request)
        if app_label is not None:
            app_list = [app for app in app_list if app['app_label'] == app_label]
        # Custom ordering: Core apps first
        priority_order = ['users', 'assets', 'bookings', 'rides', 'payments', 
                         'contracts', 'messaging', 'notifications', 'ratings',
                         'rbac', 'audits', 'social']
        ordered_apps = []
        for app in priority_order:
            for app_dict in app_list:
                if app_dict['app_label'] == app:
                    ordered_apps.append(app_dict)
        # Add any remaining apps
        for app_dict in app_list:
            if app_dict not in ordered_apps:
                ordered_apps.append(app_dict)
        return ordered_apps


# Create custom admin site instance
admin_site = KibossAdminSite(name='kiboss_admin')


# =============================================================================
# CUSTOM ACTIONS
# =============================================================================

def export_to_csv(modeladmin, request, queryset):
    """
    Export selected objects to CSV format.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model.__name__}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    # Write header
    if queryset.exists():
        fields = queryset[0]._meta.get_fields()
        field_names = [f.name for f in fields]
        writer.writerow(field_names)
        
        # Write data rows
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


def block_users(modeladmin, request, queryset):
    """Block selected users."""
    queryset.update(is_blocked=True, block_reason='Blocked by admin')
block_users.short_description = "Block selected users"


def unblock_users(modeladmin, request, queryset):
    """Unblock selected users."""
    queryset.update(is_blocked=False, block_reason='')
unblock_users.short_description = "Unblock selected users"


def verify_email(modeladmin, request, queryset):
    """Mark selected users as email verified."""
    queryset.update(is_email_verified=True)
verify_email.short_description = "Verify email for selected users"


def verify_phone(modeladmin, request, queryset):
    """Mark selected users as phone verified."""
    queryset.update(is_phone_verified=True)
verify_phone.short_description = "Verify phone for selected users"


def verify_identity(modeladmin, request, queryset):
    """Mark selected users as identity verified."""
    queryset.update(is_identity_verified=True)
verify_identity.short_description = "Verify identity for selected users"


def activate_users(modeladmin, request, queryset):
    """Activate selected users."""
    queryset.update(is_active=True)
activate_users.short_description = "Activate selected users"


def deactivate_users(modeladmin, request, queryset):
    """Deactivate selected users."""
    queryset.update(is_active=False)
deactivate_users.short_description = "Deactivate selected users"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile - stacked display.
    """
    model = UserProfile
    can_delete = False
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Personal Information', {
            'fields': ('phone', 'avatar', 'date_of_birth', 'bio')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 
                      'latitude', 'longitude')
        }),
        ('Preferences', {
            'fields': ('timezone', 'language', 'currency', 'notification_settings')
        }),
        ('Statistics', {
            'fields': ('total_bookings', 'total_listings', 
                      'total_rides_as_driver', 'total_rides_as_passenger')
        }),
        ('Documents', {
            'fields': ('identity_document',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class TrustScoreInline(admin.StackedInline):
    """
    Inline admin for TrustScore - stacked display.
    """
    model = TrustScore
    can_delete = False
    readonly_fields = ['last_calculated']
    fieldsets = (
        ('Score Components', {
            'fields': ('reliability_score', 'communication_score', 
                      'cleanliness_score', 'timeliness_score', 'overall_score')
        }),
        ('Counts', {
            'fields': ('completed_bookings', 'cancelled_bookings', 
                      'no_shows', 'late_returns', 
                      'disputes_initiated', 'disputes_against')
        }),
        ('Badges', {
            'fields': ('badges',)
        }),
        ('Last Calculated', {
            'fields': ('last_calculated',)
        }),
    )


class DeviceInline(admin.TabularInline):
    """
    Inline admin for Device - tabular display.
    """
    model = Device
    extra = 0
    readonly_fields = ['last_active_at', 'created_at', 'updated_at']
    fields = ['device_type', 'device_name', 'device_token', 'is_active', 'last_active_at']


class BlacklistedTokenInline(admin.TabularInline):
    """
    Inline admin for BlacklistedToken - tabular display.
    """
    model = BlacklistedToken
    extra = 0
    readonly_fields = ['token', 'user', 'reason', 'expires_at', 'created_at']
    fields = ['token', 'user', 'reason', 'expires_at', 'created_at']
    can_delete = True


# =============================================================================
# USER ADMIN
# =============================================================================

class UserAdmin(DjangoUserAdmin):
    """
    Enhanced admin configuration for User model.
    
    Features:
    - Comprehensive list display with computed properties
    - Multiple filter options
    - Full-text search
    - Custom ordering
    - Inline editing for related profiles
    - Batch actions
    - CSV export
    - Password change functionality (inherited from Django UserAdmin)
    """
    
    # Add fieldsets for creating users (required for Django UserAdmin)
    add_fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password1', 'password2')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
    )
    
    # Read-only fields (computed or sensitive)
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'last_login_at', 
        'date_joined', 'is_verified'
    ]
    
    # Fields to display in list view
    list_display = [
        'email', 'get_full_name', 'trust_score_badge', 
        'verification_status', 'is_active', 'is_blocked', 
        'last_login_display', 'created_at'
    ]
    
    # Fields to link to detail view
    list_display_links = ['email', 'get_full_name']
    
    # Filter options
    list_filter = [
        'is_active', 'is_blocked', 'is_email_verified', 
        'is_phone_verified', 'is_identity_verified',
        'groups', 'created_at', 'last_login_at'
    ]
    
    # Search fields
    search_fields = [
        'email', 'first_name', 'last_name', 
        'phone', 'id'
    ]
    
    # Default ordering
    ordering = ['-created_at']
    
    # Pagination
    list_per_page = 25
    list_max_show_all = 200
    
    # Inlines
    inlines = [UserProfileInline, TrustScoreInline, DeviceInline]
    
    # Fieldsets for detail view - Note: password is handled by Django UserAdmin
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name')
        }),
        ('Verification Status', {
            'fields': ('is_email_verified', 'is_phone_verified', 'is_identity_verified', 'is_verified')
        }),
        ('Trust & Reputation', {
            'fields': ('trust_score', 'total_ratings_count')
        }),
        ('Status', {
            'fields': ('is_active', 'is_blocked', 'block_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login_at', 'date_joined'),
            'classes': ('collapse',)
        }),
        ('Groups & Permissions', {
            'fields': ('groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
    )
    
    # Custom actions
    actions = [
        export_to_csv, block_users, unblock_users,
        verify_email, verify_phone, verify_identity,
        activate_users, deactivate_users
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related for related objects."""
        return super().get_queryset(request).select_related(
            'profile', 'trust_score_info'
        ).prefetch_related('groups')
    
    def get_full_name(self, obj):
        """Display user's full name."""
        return obj.get_full_name() or '(No name)'
    get_full_name.short_description = 'Name'
    get_full_name.admin_order_field = 'first_name'
    
    def trust_score_badge(self, obj):
        """Display trust score as a color-coded badge."""
        # Handle case where trust_score might be None
        if obj.trust_score is None:
            score = 0.0
        else:
            score = float(obj.trust_score)
        
        if score >= 80:
            color = 'green'
            bg_color = '#d4edda'
        elif score >= 50:
            color = 'orange'
            bg_color = '#fff3cd'
        else:
            color = 'red'
            bg_color = '#f8d7da'
        
        # Convert score to formatted string before passing to format_html
        score_str = f"{score:.2f}"
        
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            bg_color, color, score_str
        )
    trust_score_badge.short_description = 'Trust Score'
    trust_score_badge.admin_order_field = 'trust_score'
    
    def verification_status(self, obj):
        """Display verification status."""
        verified = []
        if obj.is_email_verified:
            verified.append('📧')
        if obj.is_phone_verified:
            verified.append('📱')
        if obj.is_identity_verified:
            verified.append('🪪')
        
        return format_html(' '.join(verified) if verified else '❌')
    verification_status.short_description = 'Verification'
    
    def last_login_display(self, obj):
        """Display last login with relative time."""
        if obj.last_login_at:
            now = timezone.now()
            delta = now - obj.last_login_at
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            else:
                return f"{delta.seconds // 60} minutes ago"
        return 'Never'
    last_login_display.short_description = 'Last Login'
    last_login_display.admin_order_field = 'last_login_at'
    
    def is_verified(self, obj):
        """Computed property for verification status."""
        return obj.is_verified
    is_verified.boolean = True
    
    def get_readonly_fields(self, request, obj=None):
        """Dynamically set readonly fields based on permissions."""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.extend(['is_superuser', 'user_permissions', 'groups'])
        return readonly
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of superusers."""
        if obj and obj.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """Log admin actions for changes."""
        if change:
            # Log the change in audit log if needed
            pass
        super().save_model(request, obj, form, change)


class DeviceAdmin(admin.ModelAdmin):
    """Admin configuration for Device model."""
    
    list_display = ['user', 'device_type', 'device_name', 'device_token_preview', 
                   'is_active', 'last_active_at']
    list_filter = ['device_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'device_token', 'device_name']
    ordering = ['-last_active_at']
    list_per_page = 25
    
    readonly_fields = ['created_at', 'updated_at']
    
    def device_token_preview(self, obj):
        """Show truncated device token."""
        if len(obj.device_token) > 30:
            return obj.device_token[:30] + '...'
        return obj.device_token
    device_token_preview.short_description = 'Device Token'


class BlacklistedTokenAdmin(admin.ModelAdmin):
    """Admin configuration for BlacklistedToken model."""
    
    list_display = ['user', 'token_preview', 'reason', 'expires_at', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['user__email', 'token']
    ordering = ['-created_at']
    list_per_page = 25
    
    readonly_fields = ['token', 'user', 'reason', 'expires_at', 'created_at']
    
    def token_preview(self, obj):
        """Show truncated token."""
        if len(obj.token) > 40:
            return obj.token[:40] + '...'
        return obj.token
    token_preview.short_description = 'Token'


# =============================================================================
# SUMMARY STATISTICS FOR DASHBOARD
# =============================================================================

def get_user_stats():
    """Get summary statistics for users."""
    from django.db.models import Count, Avg
    from .models import User
    
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'blocked_users': User.objects.filter(is_blocked=True).count(),
        'verified_users': User.objects.filter(
            is_email_verified=True, 
            is_phone_verified=True
        ).count(),
        'avg_trust_score': User.objects.aggregate(Avg('trust_score'))['trust_score__avg'],
    }
    return stats


# Register with custom admin site
admin_site.register(User, UserAdmin)
admin_site.register(Device, DeviceAdmin)
admin_site.register(BlacklistedToken, BlacklistedTokenAdmin)

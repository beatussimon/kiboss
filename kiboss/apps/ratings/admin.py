"""
Enhanced Django Admin Configuration for Ratings App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Rating, TrustDetails, RatingStatus, RatingCategory


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


def approve_ratings(modeladmin, request, queryset):
    """Approve selected ratings."""
    queryset.update(status=RatingStatus.APPROVED)
approve_ratings.short_description = "Approve ratings"


def reject_ratings(modeladmin, request, queryset):
    """Reject selected ratings."""
    queryset.update(status=RatingStatus.REJECTED)
reject_ratings.short_description = "Reject ratings"


def reveal_ratings(modeladmin, request, queryset):
    """Mutually reveal selected ratings."""
    for rating in queryset:
        rating.reveal_mutually()
reveal_ratings.short_description = "Reveal ratings"


# =============================================================================
# RATING ADMIN
# =============================================================================

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Rating model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at', 'revealed_at']
    list_display = [
        'id', 'reviewer', 'reviewee', 'category_badge',
        'overall_rating', 'booking', 'status_badge',
        'is_mutually_revealed', 'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'category', 'overall_rating',
        'is_mutually_revealed', 'created_at'
    ]
    
    search_fields = [
        'id', 'reviewer__email', 'reviewee__email',
        'title', 'comment', 'booking__id'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    fieldsets = (
        ('Rating Details', {
            'fields': ('id', 'booking', 'ride', 'reviewer', 'reviewee', 'category')
        }),
        ('Scores', {
            'fields': ('overall_rating', 'reliability_rating', 
                      'communication_rating', 'cleanliness_rating', 
                      'timeliness_rating')
        }),
        ('Content', {
            'fields': ('title', 'comment', 'private_feedback')
        }),
        ('Status', {
            'fields': ('status', 'is_mutually_revealed', 'revealed_at')
        }),
        ('Asset Rating', {
            'fields': ('asset_rating',)
        }),
        ('Moderation', {
            'fields': ('moderation_reason', 'moderated_by', 'moderated_at'),
            'classes': ('collapse',)
        }),
        ('Appeal', {
            'fields': ('appeal_reason', 'appealed_at', 'appeal_response'),
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
    
    actions = [export_to_csv, approve_ratings, reject_ratings, reveal_ratings]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'booking', 'ride', 'reviewer', 'reviewee', 'moderated_by'
        )
    
    def category_badge(self, obj):
        """Display category as color-coded badge."""
        category_colors = {
            'RENTER_TO_OWNER': '#28a745',
            'OWNER_TO_RENTER': '#17a2b8',
            'DRIVER_TO_PASSENGER': '#007bff',
            'PASSENGER_TO_DRIVER': '#6f42c1',
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
            'SUBMITTED': '#ffc107',
            'REVEALED': '#28a745',
            'MODERATION_PENDING': '#fd7e14',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'APPEALED': '#6f42c1',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(TrustDetails)
class TrustDetailsAdmin(admin.ModelAdmin):
    """
    Admin configuration for TrustDetails model.
    """
    
    readonly_fields = ['last_calculated']
    list_display = [
        'user', 'reliability_score', 'communication_score',
        'cleanliness_score', 'timeliness_score', 'overall_score',
        'last_calculated'
    ]
    search_fields = ['user__email']
    ordering = ['-overall_score']
    list_per_page = 25
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Score Components', {
            'fields': ('reliability_score', 'communication_score',
                      'cleanliness_score', 'timeliness_score', 'overall_score')
        }),
        ('Badges', {
            'fields': ('badges',)
        }),
        ('Last Calculated', {
            'fields': ('last_calculated',)
        }),
    )
    
    actions = [export_to_csv]


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_rating_stats():
    """Get summary statistics for ratings."""
    from django.db.models import Avg, Count
    from .models import Rating
    
    stats = {
        'total_ratings': Rating.objects.count(),
        'avg_rating': Rating.objects.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0,
        'pending_moderation': Rating.objects.filter(
            status=RatingStatus.MODERATION_PENDING
        ).count(),
        'approved_ratings': Rating.objects.filter(status=RatingStatus.APPROVED).count(),
        'rejected_ratings': Rating.objects.filter(status=RatingStatus.REJECTED).count(),
        'by_category': dict(Rating.objects.values('category').annotate(
            count=Count('id')
        ).values_list('category', 'count')),
    }
    return stats

"""
Enhanced Django Admin Configuration for Social App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse

from .models import Like, Follow, Bookmark


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
# LIKE ADMIN
# =============================================================================

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """
    Admin configuration for Like model.
    """
    
    list_display = [
        'user', 'entity_type', 'entity_id_preview',
        'created_at'
    ]
    list_filter = ['entity_type', 'created_at']
    search_fields = ['user__email', 'entity_type']
    ordering = ['-created_at']
    list_per_page = 50
    
    def entity_id_preview(self, obj):
        """Show truncated entity ID."""
        return str(obj.entity_id)[:8]
    entity_id_preview.short_description = 'Entity ID'
    
    actions = [export_to_csv]


# =============================================================================
# FOLLOW ADMIN
# =============================================================================

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """
    Admin configuration for Follow model.
    """
    
    list_display = [
        'follower', 'following', 'entity_type',
        'created_at'
    ]
    list_filter = ['entity_type', 'created_at']
    search_fields = ['follower__email', 'following__email']
    ordering = ['-created_at']
    list_per_page = 50
    
    actions = [export_to_csv]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'follower', 'following'
        )


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_social_stats():
    """Get summary statistics for social."""
    from django.db.models import Count
    
    stats = {
        'total_likes': Like.objects.count(),
        'total_follows': Follow.objects.count(),
        'total_bookmarks': Bookmark.objects.count(),
        'asset_likes': Like.objects.filter(entity_type='ASSET').count(),
        'owner_likes': Like.objects.filter(entity_type='OWNER').count(),
        'review_likes': Like.objects.filter(entity_type='REVIEW').count(),
        'owner_follows': Follow.objects.filter(entity_type='OWNER').count(),
        'driver_follows': Follow.objects.filter(entity_type='DRIVER').count(),
    }
    return stats


# =============================================================================
# BOOKMARK ADMIN
# =============================================================================

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """
    Admin configuration for Bookmark model.
    """
    
    list_display = [
        'user', 'entity_type', 'entity_id_preview',
        'created_at'
    ]
    list_filter = ['entity_type', 'created_at']
    search_fields = ['user__email', 'entity_type']
    ordering = ['-created_at']
    list_per_page = 50
    
    def entity_id_preview(self, obj):
        """Show truncated entity ID."""
        return str(obj.entity_id)[:8]
    entity_id_preview.short_description = 'Entity ID'
    
    actions = [export_to_csv]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')

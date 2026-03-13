from django.contrib import admin
from .models import Feedback, FAQ

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'category', 'is_resolved', 'created_at')
    list_filter = ('category', 'is_resolved', 'created_at')
    search_fields = ('subject', 'message', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(is_resolved=True)
    mark_as_resolved.short_description = "Mark selected as resolved"

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_active', 'order', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('question', 'answer')
    ordering = ('order',)

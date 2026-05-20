from django.contrib import admin
from django.utils import timezone
from kiboss.apps.assets.models import PromotedListing
from django.utils.html import format_html

@admin.register(PromotedListing)
class PromotionManagerAdmin(admin.ModelAdmin):
    """
    Dedicated Admin for Promotion Managers (Promoters).
    Provides easy accessibility and clean UI for handling promotions.
    """
    list_display = (
        'asset_link', 'promotion_type', 'starts_at', 'ends_at', 
        'status_pill', 'amount_paid', 'payment_reference'
    )
    list_filter = ('promotion_type', 'is_active', 'starts_at', 'ends_at')
    search_fields = ('asset__name', 'payment_reference', 'asset__owner__email')
    actions = ['approve_promotions', 'deactivate_promotions']
    
    def asset_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:assets_asset_change', args=[obj.asset.id])
        return format_html('<a href="{}">{}</a>', url, obj.asset.name)
    asset_link.short_description = 'Asset'
    asset_link.admin_order_field = 'asset__name'

    def status_pill(self, obj):
        now = timezone.now()
        is_expired = obj.ends_at < now
        
        if is_expired:
            color = "#ef4444" # red-500
            label = "EXPIRED"
        elif obj.is_active:
            color = "#22c55e" # green-500
            label = "ACTIVE"
        else:
            color = "#f59e0b" # yellow-500
            label = "PENDING"
            
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 9999px; font-weight: 800; font-size: 10px;">{}</span>',
            color, label
        )
    status_pill.short_description = 'Status'

    def approve_promotions(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} promotions have been activated.")
    approve_promotions.short_description = "✅ Activate Selected"

    def deactivate_promotions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} promotions have been deactivated.")
    deactivate_promotions.short_description = "🛑 Deactivate Selected"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('asset', 'asset__owner')

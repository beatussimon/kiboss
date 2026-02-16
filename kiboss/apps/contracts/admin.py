"""
Enhanced Django Admin Configuration for Contracts App
"""

import csv
from datetime import datetime
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Contract, ContractVersion, ContractStatus


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


def execute_contracts(modeladmin, request, queryset):
    """Execute selected contracts."""
    queryset.update(status=ContractStatus.EXECUTED)
execute_contracts.short_description = "Execute contracts"


def void_contracts(modeladmin, request, queryset):
    """Void selected contracts."""
    queryset.update(status=ContractStatus.VOIDED)
void_contracts.short_description = "Void contracts"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class ContractVersionInline(admin.TabularInline):
    """
    Inline admin for ContractVersion - tabular display.
    """
    model = ContractVersion
    extra = 0
    min_num = 0
    readonly_fields = ['created_at']
    fields = ['version', 'changes', 'created_by', 'created_at']


# =============================================================================
# CONTRACT ADMIN
# =============================================================================

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Contract model.
    """
    
    readonly_fields = [
        'id', 'version', 'generated_at', 'updated_at',
        'owner_accepted_at', 'renter_accepted_at'
    ]
    list_display = [
        'id', 'booking', 'status_badge', 'version',
        'jurisdiction', 'owner_accepted', 'renter_accepted',
        'generated_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'version', 'jurisdiction',
        'generated_at', 'updated_at'
    ]
    
    search_fields = [
        'id', 'booking__id', 'jurisdiction',
        'admin_override_reason'
    ]
    
    ordering = ['-generated_at']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [ContractVersionInline]
    
    fieldsets = (
        ('Contract Details', {
            'fields': ('id', 'booking', 'version', 'status')
        }),
        ('Snapshot', {
            'fields': ('snapshot',)
        }),
        ('Jurisdiction', {
            'fields': ('jurisdiction', 'governing_law')
        }),
        ('Terms', {
            'fields': ('terms', 'cancellation_policy', 
                      'late_return_policy', 'damage_policy')
        }),
        ('Signatures', {
            'fields': ('owner_signature', 'renter_signature')
        }),
        ('Acceptance', {
            'fields': ('owner_accepted_at', 'renter_accepted_at')
        }),
        ('Admin Override', {
            'fields': ('admin_override', 'admin_override_reason', 'admin_override_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('generated_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv, execute_contracts, void_contracts]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'booking', 'admin_override_by'
        )
    
    def owner_accepted(self, obj):
        """Display owner acceptance status."""
        return bool(obj.owner_signature)
    owner_accepted.boolean = True
    owner_accepted.short_description = 'Owner Accepted'
    
    def renter_accepted(self, obj):
        """Display renter acceptance status."""
        return bool(obj.renter_signature)
    renter_accepted.boolean = True
    renter_accepted.short_description = 'Renter Accepted'
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'PENDING': '#ffc107',
            'ACCEPTED': '#17a2b8',
            'EXECUTED': '#28a745',
            'COMPLETED': '#28a745',
            'ARCHIVED': '#6c757d',
            'VOIDED': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(ContractVersion)
class ContractVersionAdmin(admin.ModelAdmin):
    """Admin configuration for ContractVersion model."""
    
    readonly_fields = ['created_at']
    list_display = [
        'contract', 'version', 'changes_preview',
        'created_by', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['contract__id', 'changes']
    ordering = ['-created_at']
    list_per_page = 50
    
    def changes_preview(self, obj):
        """Show truncated changes."""
        if len(obj.changes) > 50:
            return obj.changes[:50] + '...'
        return obj.changes
    changes_preview.short_description = 'Changes'


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_contract_stats():
    """Get summary statistics for contracts."""
    from django.db.models import Count
    from .models import Contract
    
    stats = {
        'total_contracts': Contract.objects.count(),
        'pending_contracts': Contract.objects.filter(status=ContractStatus.PENDING).count(),
        'executed_contracts': Contract.objects.filter(status=ContractStatus.EXECUTED).count(),
        'voided_contracts': Contract.objects.filter(status=ContractStatus.VOIDED).count(),
        'by_status': dict(Contract.objects.values('status').annotate(
            count=Count('id')
        ).values_list('status', 'count')),
    }
    return stats

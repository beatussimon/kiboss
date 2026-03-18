"""
Enhanced Django Admin Configuration for Payments App

This module provides a fully-featured admin interface for payment management
with advanced features including:
- Custom list views with search, filtering, and ordering
- Inline editing for disputes
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

from .models import Payment, Dispute, PaymentStatus, OfflinePaymentMethod, SubscriptionPayment, UserPaymentMethod, ManualPayment, ManualPaymentReceipt


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


def authorize_payments(modeladmin, request, queryset):
    """Authorize selected pending payments."""
    for payment in queryset.filter(status=PaymentStatus.PENDING):
        payment.authorize(payment.amount, {'last_four': '4242', 'brand': 'VISA'})
authorize_payments.short_description = "Authorize pending payments"


def release_escrow_payments(modeladmin, request, queryset):
    """Release escrow for selected payments."""
    for payment in queryset.filter(status=PaymentStatus.ESCROW):
        payment.release_from_escrow()
release_escrow_payments.short_description = "Release escrow"


def refund_payments(modeladmin, request, queryset):
    """Refund selected payments."""
    from .models import PaymentStatus
    for payment in queryset:
        if payment.status not in [PaymentStatus.REFUNDED, PaymentStatus.FROZEN]:
            payment.refund(payment.amount, 'Admin refund')
refund_payments.short_description = "Refund payments"


def freeze_disputes(modeladmin, request, queryset):
    """Freeze payments for dispute."""
    for payment in queryset.exclude(status=PaymentStatus.FROZEN):
        payment.freeze_for_dispute()
freeze_disputes.short_description = "Freeze for dispute"


def open_disputes(modeladmin, request, queryset):
    """Open selected disputes."""
    queryset.update(status='OPEN')
open_disputes.short_description = "Open disputes"


def resolve_disputes(modeladmin, request, queryset):
    """Resolve selected disputes."""
    queryset.update(status='RESOLVED', resolved_at=timezone.now())
resolve_disputes.short_description = "Resolve disputes"


# =============================================================================
# DISPUTE INLINE
# =============================================================================

class DisputeInline(admin.StackedInline):
    """
    Inline admin for Dispute - stacked display.
    """
    model = Dispute
    extra = 0
    max_num = 1
    readonly_fields = ['created_at', 'updated_at']
    fields = ['initiated_by', 'reason', 'description', 'disputed_amount',
              'status', 'evidence', 'resolution', 'resolution_notes',
              'resolved_by', 'resolved_at']


# =============================================================================
# PAYMENT ADMIN
# =============================================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Payment model.
    """
    
    readonly_fields = [
        'id', 'zenopay_transaction_id', 'zenopay_authorization_code',
        'created_at', 'updated_at', 'escrow_held_at', 'escrow_released_at',
        'refunded_at'
    ]
    list_display = [
        'id', 'amount', 'currency', 'status_badge', 
        'payment_method', 'card_brand', 'escrow_amount',
        'refunded_amount', 'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'payment_method', 'card_brand',
        'created_at', 'escrow_held_at'
    ]
    
    search_fields = [
        'id', 'booking__id', 'zenopay_transaction_id',
        'zenopay_authorization_code', 'card_last_four'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    inlines = [DisputeInline]
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('id', 'booking', 'amount', 'currency', 'payment_method')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Zenopay References', {
            'fields': ('zenopay_transaction_id', 'zenopay_authorization_code')
        }),
        ('Card Details', {
            'fields': ('card_last_four', 'card_brand')
        }),
        ('Escrow', {
            'fields': ('escrow_amount', 'escrow_held_at', 'escrow_released_at')
        }),
        ('Refund', {
            'fields': ('refunded_amount', 'refunded_at', 'refund_reason')
        }),
        ('Penalty', {
            'fields': ('penalty_amount', 'penalty_reason')
        }),
        ('Failure Details', {
            'fields': ('failure_code', 'failure_message'),
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
        export_to_csv, authorize_payments, release_escrow_payments,
        refund_payments, freeze_disputes
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('booking')
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'PENDING': '#ffc107',
            'AUTHORIZED': '#17a2b8',
            'ESCROW': '#6c757d',
            'RELEASED': '#28a745',
            'REFUNDED': '#28a745',
            'PARTIAL_REFUND': '#ffc107',
            'FAILED': '#dc3545',
            'DISPUTED': '#fd7e14',
            'FROZEN': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Dispute model.
    """
    
    readonly_fields = ['id', 'created_at', 'updated_at', 'resolved_at']
    list_display = [
        'id', 'booking', 'initiated_by', 'reason_badge',
        'disputed_amount', 'status_badge', 
        'resolution', 'resolved_by', 'created_at'
    ]
    list_display_links = ['id']
    
    list_filter = [
        'status', 'reason', 'created_at', 'resolved_at'
    ]
    
    search_fields = [
        'id', 'booking__id', 'initiated_by__email',
        'description', 'resolution_notes'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    list_max_show_all = 500
    
    fieldsets = (
        ('Dispute Details', {
            'fields': ('id', 'booking', 'payment', 'initiated_by')
        }),
        ('Reason', {
            'fields': ('reason', 'description', 'disputed_amount')
        }),
        ('Status', {
            'fields': ('status', 'evidence')
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolution_notes', 'resolved_by', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_to_csv, open_disputes, resolve_disputes]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'booking', 'payment', 'initiated_by', 'resolved_by'
        )
    
    def reason_badge(self, obj):
        """Display reason with color coding."""
        reason_colors = {
            'DAMAGE': '#dc3545',
            'NO_SHOW': '#6c757d',
            'LATE_RETURN': '#fd7e14',
            'NOT_AS_DESCRIBED': '#ffc107',
            'CANCELLATION': '#17a2b8',
            'REFUND_NOT_RECEIVED': '#28a745',
            'OTHER': '#6c757d',
        }
        color = reason_colors.get(obj.reason, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_reason_display()
        )
    reason_badge.short_description = 'Reason'
    
    def status_badge(self, obj):
        """Display status as color-coded badge."""
        status_colors = {
            'OPEN': '#dc3545',
            'UNDER_REVIEW': '#ffc107',
            'EVIDENCE_COLLECTION': '#17a2b8',
            'RESOLVED': '#28a745',
            'CLOSED': '#6c757d',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def get_payment_stats():
    """Get summary statistics for payments."""
    from django.db.models import Sum, Count
    from .models import Payment, Dispute
    
    stats = {
        'total_payments': Payment.objects.count(),
        'pending_payments': Payment.objects.filter(status=PaymentStatus.PENDING).count(),
        'in_escrow': Payment.objects.filter(status=PaymentStatus.ESCROW).aggregate(
            Sum('escrow_amount')
        )['escrow_amount__sum'] or 0,
        'total_released': Payment.objects.filter(status=PaymentStatus.RELEASED).aggregate(
            Sum('amount')
        )['amount__sum'] or 0,
        'total_refunded': Payment.objects.filter(
            status__in=[PaymentStatus.REFUNDED, PaymentStatus.PARTIAL_REFUND]
        ).aggregate(Sum('refunded_amount'))['refunded_amount__sum'] or 0,
        'total_disputes': Dispute.objects.count(),
        'open_disputes': Dispute.objects.filter(status='OPEN').count(),
        'resolved_disputes': Dispute.objects.filter(status='RESOLVED').count(),
    }
    return stats

def approve_subscription_payment(modeladmin, request, queryset):
    """Approve selected subscription payments."""
    from datetime import timedelta
    from kiboss.apps.users.models import UserSubscription
    
    for payment in queryset.filter(status=SubscriptionPayment.Status.PENDING):
        payment.status = SubscriptionPayment.Status.APPROVED
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = request.user
        payment.admin_notes = "Approved via admin action."
        payment.save()
        
        # Activate/Update subscription
        user = payment.user
        user.account_tier = payment.plan_type
        user.save()
        
        # Create or update UserSubscription
        sub, created = UserSubscription.objects.get_or_create(
            user=user,
            defaults={
                'plan_type': payment.plan_type,
                'status': UserSubscription.Status.ACTIVE,
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=30)
            }
        )
        if not created:
            sub.plan_type = payment.plan_type
            sub.status = UserSubscription.Status.ACTIVE
            sub.start_date = timezone.now()
            sub.end_date = timezone.now() + timedelta(days=30)
            sub.save()

approve_subscription_payment.short_description = "Approve selected payments"

def reject_subscription_payment(modeladmin, request, queryset):
    """Reject selected subscription payments."""
    for payment in queryset.filter(status=SubscriptionPayment.Status.PENDING):
        payment.status = SubscriptionPayment.Status.REJECTED
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = request.user
        payment.admin_notes = "Rejected via admin action."
        payment.save()

reject_subscription_payment.short_description = "Reject selected payments"

@admin.register(OfflinePaymentMethod)
class OfflinePaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('network_name', 'payment_type', 'lipa_namba', 'payment_number', 'account_name', 'is_system_wide', 'is_active', 'display_order')
    list_filter = ('is_active', 'payment_type', 'is_system_wide')
    search_fields = ('network_name', 'payment_number', 'lipa_namba', 'account_name')
    list_editable = ('is_active', 'display_order')

    def get_readonly_fields(self, request, obj=None):
        if not (request.user.is_superuser or request.user.is_staff):
            return super().get_readonly_fields(request, obj) + ('is_system_wide',)
        return super().get_readonly_fields(request, obj)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_type', 'amount', 'status', 'created_at')
    list_filter = ('status', 'plan_type')
    search_fields = ('user__email', 'confirmation_message')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'reviewed_by')
    actions = [approve_subscription_payment, reject_subscription_payment]

@admin.register(UserPaymentMethod)
class UserPaymentMethodAdmin(admin.ModelAdmin):
    """Admin for user-configured payment methods."""
    list_display = ('user', 'payment_type', 'account_name', 'account_number', 'is_active', 'is_default', 'created_at')
    list_filter = ('is_active', 'is_default', 'payment_type')
    search_fields = ('user__email', 'account_name', 'account_number')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(ManualPayment)
class ManualPaymentAdmin(admin.ModelAdmin):
    """Admin for manual payments on bookings."""
    list_display = ('id', 'booking_type', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('status', 'booking_type', 'currency')
    search_fields = ('id', 'transaction_id', 'confirmation_message')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'reviewed_by')
    
    actions = ['approve_manual_payment', 'reject_manual_payment']
    
    def approve_manual_payment(self, request, queryset):
        """Approve selected manual payments."""
        for payment in queryset.filter(status=ManualPayment.Status.PENDING):
            payment.status = ManualPayment.Status.APPROVED
            payment.reviewed_at = timezone.now()
            payment.reviewed_by = request.user
            payment.admin_notes = "Approved via admin action."
            payment.save()
            
            # Update booking status
            try:
                booking = payment.booking
                if payment.booking_type == 'ASSET':
                    from kiboss.apps.bookings.services import BookingService
                    BookingService.confirm_booking(booking.id, request.user)
                elif payment.booking_type == 'RIDE':
                    from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
                    booking.status = SeatBookingStatus.CONFIRMED
                    booking.save()
            except Exception:
                pass
    
    approve_manual_payment.short_description = "Approve selected payments"
    
    def reject_manual_payment(self, request, queryset):
        """Reject selected manual payments."""
        for payment in queryset.filter(status=ManualPayment.Status.PENDING):
            payment.status = ManualPayment.Status.REJECTED
            payment.reviewed_at = timezone.now()
            payment.reviewed_by = request.user
            payment.admin_notes = "Rejected via admin action."
            payment.save()
    
    reject_manual_payment.short_description = "Reject selected payments"

@admin.register(ManualPaymentReceipt)
class ManualPaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('transaction_reference', 'uploaded_by', 'content_type', 'object_id', 'status', 'created_at')
    list_filter = ('status', 'content_type', 'created_at')
    search_fields = ('transaction_reference', 'sender_phone_number', 'uploaded_by__email')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_receipts', 'reject_receipts']

    def approve_receipts(self, request, queryset):
        queryset.update(status=ManualPaymentReceipt.Status.APPROVED)
    approve_receipts.short_description = "Approve selected receipts"

    def reject_receipts(self, request, queryset):
        queryset.update(status=ManualPaymentReceipt.Status.REJECTED)
    reject_receipts.short_description = "Reject selected receipts"


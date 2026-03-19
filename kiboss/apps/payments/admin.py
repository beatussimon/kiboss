from django.contrib import admin
from .models import (
    Payment, 
    Dispute, 
    OfflinePaymentMethod, 
    SubscriptionPayment, 
    UserPaymentMethod, 
    ManualPayment, 
    ManualPaymentReceipt
)

@admin.action(description='Approve selected payments')
def approve_payments(modeladmin, request, queryset):
    queryset.update(status='APPROVED')

@admin.action(description='Reject selected payments')
def reject_payments(modeladmin, request, queryset):
    queryset.update(status='REJECTED')

@admin.register(OfflinePaymentMethod)
class OfflinePaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('network_name', 'payment_type', 'payment_number', 'lipa_namba', 'is_system_wide', 'is_active')
    list_filter = ('is_system_wide', 'payment_type')

@admin.register(ManualPaymentReceipt)
class ManualPaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('transaction_reference', 'status', 'uploaded_by', 'sender_phone_number', 'created_at')
    actions = [approve_payments, reject_payments]

@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_type', 'amount', 'status', 'created_at')
    actions = [approve_payments, reject_payments]

@admin.register(UserPaymentMethod)
class UserPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'payment_type', 'account_name', 'account_number', 'is_active', 'is_default')

@admin.register(ManualPayment)
class ManualPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_type', 'amount', 'status', 'created_at')
    actions = [approve_payments, reject_payments]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'currency', 'status', 'payment_method', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'initiated_by', 'status', 'resolution')
    readonly_fields = ('id', 'created_at', 'updated_at', 'resolved_at')

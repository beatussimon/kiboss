from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, UserProfile, CorporateProfile, BusinessSubscription,
    TrustScore, Device, BlacklistedToken, UserSubscription
)
from kiboss.apps.rbac.models import UserRole

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class CorporateProfileInline(admin.StackedInline):
    model = CorporateProfile
    can_delete = False
    verbose_name_plural = 'Corporate Profile'

class TrustScoreInline(admin.StackedInline):
    model = TrustScore
    can_delete = False
    verbose_name_plural = 'Trust Score'

class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = 'user'
    extra = 1
    fields = ('role', 'scope_type', 'scope_id', 'expires_at')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'verification_tier', 'trust_score')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'verification_tier')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = (UserProfileInline, CorporateProfileInline, TrustScoreInline, UserRoleInline)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Verification', {'fields': ('is_email_verified', 'is_phone_verified', 'is_identity_verified', 'verification_tier')}),
        ('Trust & Safety', {'fields': ('trust_score', 'total_ratings_count', 'is_blocked', 'block_reason')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if isinstance(instance, UserRole) and not getattr(instance, 'created_by_id', None):
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()

@admin.register(CorporateProfile)
class CorporateProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'business_category', 'registration_number', 'verification_status', 'created_at')
    list_filter = ('business_category', 'verification_status')
    search_fields = ('company_name', 'registration_number', 'user__email')

@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'plan_type', 'status', 'amount_paid', 'start_date', 'end_date')
    list_filter = ('status', 'plan_type')
    search_fields = ('profile__company_name', 'payment_reference')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'device_type', 'is_active', 'last_active_at')
    list_filter = ('device_type', 'is_active')
    search_fields = ('user__email', 'device_name', 'device_token')

@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'expires_at', 'created_at')
    list_filter = ('reason',)
    search_fields = ('user__email', 'token')

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_type', 'status', 'start_date', 'end_date')
    list_filter = ('plan_type', 'status')
    search_fields = ('user__email',)

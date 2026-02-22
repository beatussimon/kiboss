from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, UserProfile, CorporateProfile, BusinessSubscription,
    TrustScore, Device, BlacklistedToken
)

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

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'verification_tier', 'trust_score')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'verification_tier')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = (UserProfileInline, CorporateProfileInline, TrustScoreInline)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Verification', {'fields': ('is_email_verified', 'is_phone_verified', 'is_identity_verified', 'verification_tier')}),
        ('Trust & Safety', {'fields': ('trust_score', 'total_ratings_count', 'is_blocked', 'block_reason')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

@admin.register(CorporateProfile)
class CorporateProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'registration_number', 'verification_status', 'created_at')
    list_filter = ('verification_status',)
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

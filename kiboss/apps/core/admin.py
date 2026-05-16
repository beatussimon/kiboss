"""
KIBOSS Custom Admin Configuration

This module provides the custom admin site with enhanced features:
- Custom branding and theming
- Dashboard with summary statistics
- Quick action links
- Enhanced app ordering

Usage:
    Replace the default admin.site with our custom KibossAdminSite
    in your urls.py:
        
        from kiboss.apps.core.admin import admin_site
        urlpatterns = [
            path('admin/', admin_site.urls),
        ]
"""

from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.utils import timezone


# =============================================================================
# KIBOSS CUSTOM ADMIN SITE
# =============================================================================

class KibossAdminSite(AdminSite):
    """
    Custom admin site for KIBOSS with enhanced features.
    
    Features:
    - Custom branding and theming
    - Dashboard with summary statistics
    - Quick action links
    - Enhanced app ordering
    """
    
    site_header = 'KIBOSS Administration'
    site_title = 'KIBOSS Admin Portal'
    index_title = 'Dashboard Overview'
    index_template = 'admin/kiboss_index.html'
    
    def get_app_list(self, request, app_label=None):
        """
        Return sorted app list with custom ordering.
        Prioritizes core business apps first.
        """
        app_list = super().get_app_list(request)
        
        # Custom ordering: Core apps first
        priority_order = [
            'users', 'assets', 'bookings', 'rides', 'payments',
            'contracts', 'messaging', 'notifications', 'ratings',
            'rbac', 'audits', 'social'
        ]
        
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
    
    def index(self, request, extra_context=None):
        """
        Override index view to include custom dashboard with statistics.
        """
        # Collect statistics from all apps
        stats = {}
        
        # User stats
        try:
            from kiboss.apps.users.models import User
            stats['users'] = {
                'total': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'blocked': User.objects.filter(is_blocked=True).count(),
                'verified': User.objects.filter(
                    is_email_verified=True, is_phone_verified=True
                ).count(),
            }
        except Exception:
            stats['users'] = {'total': 'N/A'}
        
        # Asset stats
        try:
            from kiboss.apps.assets.models import Asset, VerificationStatus
            stats['assets'] = {
                'total': Asset.objects.count(),
                'active': Asset.objects.filter(is_active=True).count(),
                'pending_verification': Asset.objects.filter(
                    verification_status=VerificationStatus.PENDING
                ).count(),
                'verified': Asset.objects.filter(
                    verification_status=VerificationStatus.VERIFIED
                ).count(),
            }
        except Exception:
            stats['assets'] = {'total': 'N/A'}
        
        # Booking stats
        try:
            from kiboss.apps.bookings.models import Booking, BookingStatus
            from django.db.models import Sum
            stats['bookings'] = {
                'total': Booking.objects.count(),
                'pending': Booking.objects.filter(status=BookingStatus.PENDING).count(),
                'confirmed': Booking.objects.filter(status=BookingStatus.CONFIRMED).count(),
                'active': Booking.objects.filter(status=BookingStatus.ACTIVE).count(),
                'completed': Booking.objects.filter(status=BookingStatus.COMPLETED).count(),
                'total_revenue': Booking.objects.filter(
                    status__in=[BookingStatus.COMPLETED, BookingStatus.ACTIVE]
                ).aggregate(Sum('total_price'))['total_price__sum'] or 0,
            }
        except Exception:
            stats['bookings'] = {'total': 'N/A'}
        
        # Ride stats
        try:
            from kiboss.apps.rides.models import Ride, RideStatus
            stats['rides'] = {
                'total': Ride.objects.count(),
                'scheduled': Ride.objects.filter(status=RideStatus.SCHEDULED).count(),
                'open': Ride.objects.filter(status=RideStatus.OPEN).count(),
                'in_transit': Ride.objects.filter(status=RideStatus.IN_TRANSIT).count(),
                'completed': Ride.objects.filter(status=RideStatus.COMPLETED).count(),
            }
        except Exception:
            stats['rides'] = {'total': 'N/A'}
        
        # Payment stats
        try:
            from kiboss.apps.payments.models import Payment, PaymentStatus
            from django.db.models import Sum
            stats['payments'] = {
                'total': Payment.objects.count(),
                'in_escrow': Payment.objects.filter(
                    status=PaymentStatus.ESCROW
                ).aggregate(Sum('escrow_amount'))['escrow_amount__sum'] or 0,
                'total_released': Payment.objects.filter(
                    status=PaymentStatus.RELEASED
                ).aggregate(Sum('amount'))['amount__sum'] or 0,
            }
        except Exception:
            stats['payments'] = {'total': 'N/A'}
        
        # Dispute stats
        try:
            from kiboss.apps.payments.models import Dispute
            stats['disputes'] = {
                'total': Dispute.objects.count(),
                'open': Dispute.objects.filter(status='OPEN').count(),
                'resolved': Dispute.objects.filter(status='RESOLVED').count(),
            }
        except Exception:
            stats['disputes'] = {'total': 'N/A'}
        
        # Rating stats
        try:
            from kiboss.apps.ratings.models import Rating, RatingStatus
            from django.db.models import Avg
            stats['ratings'] = {
                'total': Rating.objects.count(),
                'avg_rating': Rating.objects.aggregate(
                    Avg('overall_rating')
                )['overall_rating__avg'] or 0,
                'pending_moderation': Rating.objects.filter(
                    status=RatingStatus.MODERATION_PENDING
                ).count(),
            }
        except Exception:
            stats['ratings'] = {'total': 'N/A'}
        
        # Messaging stats
        try:
            from kiboss.apps.messaging.models import Thread, Message
            stats['messaging'] = {
                'total_threads': Thread.objects.count(),
                'open_threads': Thread.objects.filter(status='OPEN').count(),
                'flagged': Thread.objects.filter(is_flagged=True).count(),
                'total_messages': Message.objects.count(),
            }
        except Exception:
            stats['messaging'] = {'total_threads': 'N/A'}
        
        # Audit stats
        try:
            from kiboss.apps.audits.models import AuditLog
            today = timezone.now().date()
            stats['audits'] = {
                'total': AuditLog.objects.count(),
                'today': AuditLog.objects.filter(created_at__date=today).count(),
                'failed': AuditLog.objects.filter(success=False).count(),
            }
        except Exception:
            stats['audits'] = {'total': 'N/A'}
        
        # Extra context
        extra_context = extra_context or {}
        extra_context['kiboss_stats'] = stats
        extra_context['current_time'] = timezone.now()
        
        return super().index(request, extra_context)


# Create custom admin site instance
admin_site = KibossAdminSite(name='kiboss_admin')


# =============================================================================
# AUTO-REGISTER MODELS
# =============================================================================

def register_all_models():
    """
    Register all models with the custom admin site.
    This function is called automatically when this module is imported.
    """
    
    # Users App
    from kiboss.apps.users.models import (
        User, UserProfile, TrustScore, Device, BlacklistedToken,
        UserSubscription, CorporateProfile, BusinessSubscription, CorporateWorker
    )
    from kiboss.apps.users.verification_models import (
        VerificationRequest, VerificationDocument, VerificationLog
    )
    from kiboss.apps.users.admin import (
        UserAdmin, DeviceAdmin, BlacklistedTokenAdmin,
        UserSubscriptionAdmin, CorporateProfileAdmin, BusinessSubscriptionAdmin
    )
    from kiboss.apps.core.models import SystemConfiguration
    from django.contrib.admin import ModelAdmin

    class SystemConfigAdmin(ModelAdmin):
        fieldsets = [
            ('Business Tiers', {'fields': [
                'business_registration_fee',
                'business_subscription_monthly',
                'business_subscription_yearly',
                'business_terms_conditions',
            ]}),
            ('Landing Page', {'fields': [
                'hero_image',
                'hero_image_url',
            ], 'description': 'Upload a hero image OR provide an external URL. URL takes priority.'}),
        ]

    class VerificationRequestAdmin(ModelAdmin):
        list_display = ('user', 'verification_type', 'status', 'created_at', 'reviewed_at')
        list_filter = ('verification_type', 'status')
        search_fields = ('user__email', 'document_number')
        readonly_fields = ('created_at', 'updated_at')

    admin_site.register(User, UserAdmin)
    admin_site.register(UserProfile, ModelAdmin)
    admin_site.register(TrustScore, ModelAdmin)
    admin_site.register(Device, DeviceAdmin)
    admin_site.register(BlacklistedToken, BlacklistedTokenAdmin)
    admin_site.register(SystemConfiguration, SystemConfigAdmin)
    admin_site.register(UserSubscription, UserSubscriptionAdmin)
    admin_site.register(CorporateProfile, CorporateProfileAdmin)
    admin_site.register(BusinessSubscription, BusinessSubscriptionAdmin)
    admin_site.register(CorporateWorker, ModelAdmin)
    admin_site.register(VerificationRequest, VerificationRequestAdmin)
    admin_site.register(VerificationDocument, ModelAdmin)
    admin_site.register(VerificationLog, ModelAdmin)
    
    # Assets App
    from kiboss.apps.assets.models import (
        Asset, AssetPhoto, AssetPricing, AssetAvailability,
        AssetCapacity, AssetTimeGranularity, AssetJurisdiction
    )
    from kiboss.apps.assets.admin import (
        AssetAdmin, AssetPhotoAdmin, AssetPricingAdmin, AssetAvailabilityAdmin,
        AssetCapacityAdmin, AssetTimeGranularityAdmin, AssetJurisdictionAdmin
    )
    
    admin_site.register(Asset, AssetAdmin)
    admin_site.register(AssetPhoto, AssetPhotoAdmin)
    admin_site.register(AssetPricing, AssetPricingAdmin)
    admin_site.register(AssetAvailability, AssetAvailabilityAdmin)
    admin_site.register(AssetCapacity, AssetCapacityAdmin)
    admin_site.register(AssetTimeGranularity, AssetTimeGranularityAdmin)
    admin_site.register(AssetJurisdiction, AssetJurisdictionAdmin)
    
    # Bookings App
    from kiboss.apps.bookings.models import (
        Booking, BookingStatusTransition, BookingTimeline, BookingLock
    )
    from kiboss.apps.bookings.admin import (
        BookingAdmin, BookingStatusTransitionAdmin, 
        BookingTimelineAdmin, BookingLockAdmin
    )
    
    admin_site.register(Booking, BookingAdmin)
    admin_site.register(BookingStatusTransition, BookingStatusTransitionAdmin)
    admin_site.register(BookingTimeline, BookingTimelineAdmin)
    admin_site.register(BookingLock, BookingLockAdmin)
    
    # Rides App
    from kiboss.apps.rides.models import (
        Ride, RideStop, SeatBooking, RideSchedule
    )
    from kiboss.apps.rides.admin import (
        RideAdmin, RideStopAdmin, SeatBookingAdmin, RideScheduleAdmin
    )
    
    admin_site.register(Ride, RideAdmin)
    admin_site.register(RideStop, RideStopAdmin)
    admin_site.register(SeatBooking, SeatBookingAdmin)
    admin_site.register(RideSchedule, RideScheduleAdmin)
    
    # Payments App
    from kiboss.apps.payments.models import (
        Payment, Dispute, OfflinePaymentMethod,
        UserPaymentMethod, ManualPayment
    )
    from kiboss.apps.payments.admin import (
        PaymentAdmin, DisputeAdmin, OfflinePaymentMethodAdmin,
        UserPaymentMethodAdmin, ManualPaymentAdmin
    )
    
    admin_site.register(Payment, PaymentAdmin)
    admin_site.register(Dispute, DisputeAdmin)
    admin_site.register(OfflinePaymentMethod, OfflinePaymentMethodAdmin)
    admin_site.register(UserPaymentMethod, UserPaymentMethodAdmin)
    admin_site.register(ManualPayment, ManualPaymentAdmin)

    
    # Contracts App
    from kiboss.apps.contracts.models import Contract, ContractVersion
    from kiboss.apps.contracts.admin import ContractAdmin, ContractVersionAdmin
    
    admin_site.register(Contract, ContractAdmin)
    admin_site.register(ContractVersion, ContractVersionAdmin)
    
    # Messaging App
    from kiboss.apps.messaging.models import (
        Thread, Message, MessageAttachment, MessageRateLimit
    )
    from kiboss.apps.messaging.admin import (
        ThreadAdmin, MessageAdmin, MessageAttachmentAdmin, MessageRateLimitAdmin
    )
    
    admin_site.register(Thread, ThreadAdmin)
    admin_site.register(Message, MessageAdmin)
    admin_site.register(MessageAttachment, MessageAttachmentAdmin)
    admin_site.register(MessageRateLimit, MessageRateLimitAdmin)
    
    # Notifications App
    from kiboss.apps.notifications.models import Notification, NotificationPreference
    from kiboss.apps.notifications.admin import (
        NotificationAdmin, NotificationPreferenceAdmin
    )
    
    admin_site.register(Notification, NotificationAdmin)
    admin_site.register(NotificationPreference, NotificationPreferenceAdmin)
    
    # Ratings App
    from kiboss.apps.ratings.models import Rating
    from kiboss.apps.ratings.admin import RatingAdmin
    
    admin_site.register(Rating, RatingAdmin)
    
    # RBAC App
    from kiboss.apps.rbac.models import RolePermission, UserRole, AdminAction
    from kiboss.apps.rbac.admin import (
        RolePermissionAdmin, UserRoleAdmin, AdminActionAdmin
    )
    
    admin_site.register(RolePermission, RolePermissionAdmin)
    admin_site.register(UserRole, UserRoleAdmin)
    admin_site.register(AdminAction, AdminActionAdmin)
    
    # Audits App
    from kiboss.apps.audits.models import AuditLog
    from kiboss.apps.audits.admin import AuditLogAdmin
    
    admin_site.register(AuditLog, AuditLogAdmin)
    
    # Social App
    from kiboss.apps.social.models import Like, Follow
    from kiboss.apps.social.admin import LikeAdmin, FollowAdmin
    
    admin_site.register(Like, LikeAdmin)
    admin_site.register(Follow, FollowAdmin)


# Try to auto-register (will work when all models are loaded)
try:
    register_all_models()
except ImportError:
    # Models might not be loaded yet, apps should call this manually
    pass

from django.db.models.signals import post_save
from django.dispatch import receiver

from kiboss.apps.users.models import User, UserProfile, TrustScore


@receiver(post_save, sender=User)
def ensure_profile_and_trust(sender, instance, created, **kwargs):
    """Guarantee every user has profile and trust score records."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        TrustScore.objects.get_or_create(user=instance)

from django.db.models.signals import pre_save
from kiboss.apps.users.models import CorporateProfile

@receiver(pre_save, sender=CorporateProfile)
def notify_corporate_profile_status(sender, instance, **kwargs):
    """Notify the user when their business verification status updates."""
    if not instance.pk:
        return
        
    try:
        old_instance = CorporateProfile.objects.get(pk=instance.pk)
    except CorporateProfile.DoesNotExist:
        return
        
    if old_instance.verification_status != instance.verification_status:
        from kiboss.apps.notifications.services import NotificationService
        from kiboss.apps.notifications.models import NotificationCategory
        
        if instance.verification_status == 'VERIFIED':
            NotificationService.create_notification(
                user=instance.user,
                category=NotificationCategory.SYSTEM,
                notification_type='BUSINESS_VERIFIED',
                title="Business Verified",
                message=f"Congratulations! Your business '{instance.company_name}' has been verified."
            )
        elif instance.verification_status == 'REJECTED':
            NotificationService.create_notification(
                user=instance.user,
                category=NotificationCategory.SYSTEM,
                notification_type='BUSINESS_REJECTED',
                title="Business Application Rejected",
                message=f"Your application for '{instance.company_name}' was rejected. Please review your dashboard for details."
            )

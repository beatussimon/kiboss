"""
Celery Tasks for Users App
"""

from celery import shared_task
from django.utils import timezone
from kiboss.apps.users.models import UserSubscription, BusinessSubscription
from kiboss.apps.assets.models import Asset

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_expired_subscriptions(self):
    """
    Routinely check for expired User and Business subscriptions
    and update their statuses to EXPIRED.
    """
    now = timezone.now()

    # Expire UserSubscriptions
    expired_user_subs = UserSubscription.objects.filter(
        status=UserSubscription.Status.ACTIVE,
        end_date__lt=now
    )
    user_subs_count = expired_user_subs.update(status=UserSubscription.Status.EXPIRED)

    # Expire BusinessSubscriptions
    expired_business_subs = BusinessSubscription.objects.filter(
        status=BusinessSubscription.Status.ACTIVE,
        end_date__lt=now
    )
    business_subs_count = expired_business_subs.update(status=BusinessSubscription.Status.EXPIRED)

    return f"Expired {user_subs_count} user subscriptions and {business_subs_count} business subscriptions."

@shared_task
def expire_subscriptions():
    """
    [T2-11] Comprehensive subscription expiry task.
    Handles tier downgrades and asset delisting.
    """
    expired_user_subs = UserSubscription.objects.filter(status='ACTIVE', end_date__lt=timezone.now())
    for sub in expired_user_subs:
        sub.status = 'EXPIRED'
        sub.save()
        sub.user.account_tier = 'FREE'
        sub.user.save(update_fields=['account_tier', 'updated_at'])
        
        # Delist excess assets (keep only first 3)
        excess_assets = Asset.objects.filter(owner=sub.user, is_listed=True).order_by('-created_at')[3:]
        for asset in excess_assets:
            asset.is_listed = False
            asset.save(update_fields=['is_listed'])
            
    return f"Processed {expired_user_subs.count()} expired subscriptions."

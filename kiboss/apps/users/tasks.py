"""
Celery Tasks for Users App
"""

from celery import shared_task
from django.utils import timezone
from kiboss.apps.users.models import UserSubscription, BusinessSubscription

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

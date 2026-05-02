"""
Subscription Service for KIBOSS
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

class SubscriptionService:
    @classmethod
    def activate(cls, subscription, confirmed_by):
        """Activate a pending subscription after payment approval."""
        with transaction.atomic():
            duration_days = 30
            # Handle both UserSubscription and BusinessSubscription if they share plan_type
            plan_type = getattr(subscription, 'plan_type', 'PLUS')
            if plan_type == 'YEARLY':
                duration_days = 365
                
            subscription.status = 'ACTIVE'
            subscription.start_date = timezone.now()
            subscription.end_date = timezone.now() + timedelta(days=duration_days)
            subscription.save()
            
            # If it's a UserSubscription, upgrade the user's account tier
            if hasattr(subscription, 'user'):
                user = subscription.user
                user.account_tier = plan_type
                user.save(update_fields=['account_tier', 'updated_at'])
            # If it's a BusinessSubscription, upgrade the corporate profile
            elif hasattr(subscription, 'profile'):
                profile = subscription.profile
                profile.user.account_tier = 'BUSINESS' # or some relevant tier
                profile.user.save(update_fields=['account_tier', 'updated_at'])
            
            return subscription

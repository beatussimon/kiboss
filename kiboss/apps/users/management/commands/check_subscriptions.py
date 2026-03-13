from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from kiboss.apps.users.models import UserSubscription, User
from kiboss.apps.notifications.services import NotificationService

class Command(BaseCommand):
    help = 'Checks user subscriptions for expiry and sends warnings.'

    def handle(self, *args, **options):
        now = timezone.now()
        warning_time = now + timedelta(days=2)
        
        # 1. Expire past subscriptions
        expired_subs = UserSubscription.objects.filter(
            status=UserSubscription.Status.ACTIVE,
            end_date__lte=now
        )
        for sub in expired_subs:
            sub.status = UserSubscription.Status.EXPIRED
            sub.save()
            
            # Revert user to FREE if currently this tier
            user = sub.user
            if user.account_tier == sub.plan_type:
                user.account_tier = 'FREE'
                user.save()
                
            NotificationService.create(
                user=user,
                notification_type='SYSTEM',
                title='Subscription Expired',
                message=f'Your {sub.plan_type} subscription has expired. You have been downgraded to the Free Plan.'
            )
            self.stdout.write(self.style.WARNING(f"Expired subscription for {user.email}"))

        # 2. Warning for impending expiry (between 47 and 48 hours to avoid spamming if run hourly)
        warnings_to_send = UserSubscription.objects.filter(
            status=UserSubscription.Status.ACTIVE,
            end_date__gt=now,
            end_date__lte=warning_time
        )
        
        for sub in warnings_to_send:
            has_been_warned = sub.user.notifications.filter(
                title__contains='Subscription Expiring',
                created_at__gte=now - timedelta(days=3)
            ).exists()
            
            if not has_been_warned:
                NotificationService.create(
                    user=sub.user,
                    notification_type='SYSTEM',
                    title='Subscription Expiring Soon',
                    message=f'Your {sub.plan_type} subscription expires in less than 2 days. Renew to keep your limits!'
                )
                self.stdout.write(self.style.SUCCESS(f"Sent expiry warning to {sub.user.email}"))

        self.stdout.write(self.style.SUCCESS('Successfully completed subscription checks.'))

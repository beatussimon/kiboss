import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from kiboss.apps.users.models import BusinessSubscription, CorporateProfile
from kiboss.apps.rides.models import Ride
from kiboss.apps.assets.models import Asset, AssetType

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Expires old subscriptions, stale rides, and inactive assets.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # 1. Expire Subscriptions
        expired_subs = BusinessSubscription.objects.filter(
            end_date__lt=now, 
            status='ACTIVE'
        )
        sub_count = expired_subs.count()
        if sub_count > 0:
            with transaction.atomic():
                for sub in expired_subs:
                    sub.status = 'EXPIRED'
                    sub.save(update_fields=['status'])
                    
                    # Downgrade user account tier if necessary
                    user = sub.corporate_profile.user
                    user.account_tier = 'FREE'
                    user.save(update_fields=['account_tier'])
            self.stdout.write(self.style.SUCCESS(f'Expired {sub_count} subscriptions.'))
        else:
            self.stdout.write('No subscriptions to expire.')

        # 2. Complete/Expire Stale Rides
        # Consider rides that departed over 24 hours ago
        stale_threshold = now - timezone.timedelta(hours=24)
        stale_rides = Ride.objects.filter(
            departure_time__lt=stale_threshold,
            status__in=['SCHEDULED', 'OPEN']
        )
        ride_count = stale_rides.count()
        if ride_count > 0:
            stale_rides.update(status='COMPLETED')
            self.stdout.write(self.style.SUCCESS(f'Auto-completed {ride_count} stale rides.'))
        else:
            self.stdout.write('No stale rides to process.')

        self.stdout.write(self.style.SUCCESS('Expiry processing complete.'))

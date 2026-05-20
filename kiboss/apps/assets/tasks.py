from celery import shared_task
from django.utils import timezone
from kiboss.apps.assets.models import PromotedListing
import logging

logger = logging.getLogger(__name__)

@shared_task(name='kiboss.apps.assets.tasks.cleanup_expired_promotions')
def cleanup_expired_promotions():
    """
    Deactivate promotions that have passed their ends_at time.
    Runs daily or hourly via Celery Beat.
    """
    from kiboss.apps.assets.models import Asset
    now = timezone.now()
    
    # Get IDs of assets whose promotions are about to expire
    expired_promos = PromotedListing.objects.filter(
        is_active=True,
        ends_at__lt=now
    )
    affected_asset_ids = list(expired_promos.values_list('asset_id', flat=True))
    
    # Deactivate them
    expired_count = expired_promos.update(is_active=False)
    
    if expired_count > 0:
        # Sync asset flags
        for asset_id in set(affected_asset_ids):
            try:
                asset = Asset.objects.get(id=asset_id)
                from kiboss.apps.assets.signals import _sync_asset_promotion
                _sync_asset_promotion(asset)
            except Asset.DoesNotExist:
                continue
                
        logger.info(f"Automatically deactivated {expired_count} expired promotions and synced {len(set(affected_asset_ids))} assets.")
    
    return expired_count

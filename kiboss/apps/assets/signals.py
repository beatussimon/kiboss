from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from kiboss.apps.assets.models import Asset, PromotedListing
from kiboss.apps.users.models import UserProfile


def _update_listing_count(owner):
    profile, _ = UserProfile.objects.get_or_create(user=owner)
    profile.total_listings = owner.assets.filter(is_active=True).count()
    profile.save(update_fields=['total_listings', 'updated_at'])


def _sync_asset_promotion(asset):
    """Update the is_promoted flag on the Asset based on current active promotions."""
    now = timezone.now()
    is_promoted = asset.promotions.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gte=now
    ).exists()
    
    if asset.is_promoted != is_promoted:
        asset.is_promoted = is_promoted
        asset.save(update_fields=['is_promoted', 'updated_at'])


@receiver(post_save, sender=Asset)
def update_profile_listings_on_save(sender, instance, **kwargs):
    _update_listing_count(instance.owner)


@receiver(post_delete, sender=Asset)
def update_profile_listings_on_delete(sender, instance, **kwargs):
    _update_listing_count(instance.owner)


@receiver(post_save, sender=PromotedListing)
def sync_promotion_on_save(sender, instance, **kwargs):
    _sync_asset_promotion(instance.asset)


@receiver(post_delete, sender=PromotedListing)
def sync_promotion_on_delete(sender, instance, **kwargs):
    _sync_asset_promotion(instance.asset)

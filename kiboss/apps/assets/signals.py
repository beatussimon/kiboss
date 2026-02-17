from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from kiboss.apps.assets.models import Asset
from kiboss.apps.users.models import UserProfile


def _update_listing_count(owner):
    profile, _ = UserProfile.objects.get_or_create(user=owner)
    profile.total_listings = owner.assets.filter(is_active=True).count()
    profile.save(update_fields=['total_listings', 'updated_at'])


@receiver(post_save, sender=Asset)
def update_profile_listings_on_save(sender, instance, **kwargs):
    _update_listing_count(instance.owner)


@receiver(post_delete, sender=Asset)
def update_profile_listings_on_delete(sender, instance, **kwargs):
    _update_listing_count(instance.owner)

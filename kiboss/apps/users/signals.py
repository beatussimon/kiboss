from django.db.models.signals import post_save
from django.dispatch import receiver

from kiboss.apps.users.models import User, UserProfile, TrustScore


@receiver(post_save, sender=User)
def ensure_profile_and_trust(sender, instance, created, **kwargs):
    """Guarantee every user has profile and trust score records."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        TrustScore.objects.get_or_create(user=instance)

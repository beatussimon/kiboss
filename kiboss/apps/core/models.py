import uuid
from django.db import models

class SystemConfiguration(models.Model):
    """
    Singleton model for global system settings.
    Adjustable via Django Admin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Business Tier Settings
    business_registration_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=50000.00,
        help_text="One-time registration fee if subscription is not used"
    )
    business_subscription_monthly = models.DecimalField(
        max_digits=12, decimal_places=2, default=15000.00,
        help_text="Monthly subscription price for Business Tier"
    )
    business_subscription_yearly = models.DecimalField(
        max_digits=12, decimal_places=2, default=150000.00,
        help_text="Yearly subscription price for Business Tier (Discounted)"
    )
    
    business_terms_conditions = models.TextField(
        default="Standard KIBOSS Business Terms: All assets must be verified. Stamped legal documents required.",
        help_text="Terms and conditions shown during business registration"
    )

    # Landing Page Hero
    hero_image = models.ImageField(
        upload_to='hero/', blank=True, null=True,
        help_text="Upload a custom hero background image for the landing page"
    )
    hero_image_url = models.URLField(
        blank=True,
        help_text="External URL for hero image (overrides uploaded image if set)"
    )

    # Global Config
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configuration"

    def save(self, *args, **kwargs):
        """Ensure only one configuration exists."""
        self.pk = uuid.UUID('00000000-0000-0000-0000-000000000001') # Constant ID for singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Helper to get or create the singleton config."""
        config, _ = cls.objects.get_or_create(
            pk=uuid.UUID('00000000-0000-0000-0000-000000000001')
        )
        return config

    def __str__(self):
        return "Global System Configuration"

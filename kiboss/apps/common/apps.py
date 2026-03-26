from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kiboss.apps.common'
    verbose_name = 'Common'

    def ready(self):
        # Warm the checkmark cache in Redis on startup
        from .checkmarks import warm_checkmark_cache
        try:
            warm_checkmark_cache()
        except Exception:
            # Prevent startup failure if Redis is down
            pass

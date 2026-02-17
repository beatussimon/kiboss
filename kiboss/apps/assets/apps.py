from django.apps import AppConfig


class AssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kiboss.apps.assets'
    verbose_name = 'Assets'

    def ready(self):
        import kiboss.apps.assets.signals  # noqa: F401

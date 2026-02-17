from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kiboss.apps.users'
    verbose_name = 'Users'

    def ready(self):
        import kiboss.apps.users.signals  # noqa: F401

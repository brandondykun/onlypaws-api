from django.apps import AppConfig


class ProfileAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.profile_app'
    verbose_name = 'Profile Management'

    def ready(self):
        import apps.profile_app.signals  # noqa: F401


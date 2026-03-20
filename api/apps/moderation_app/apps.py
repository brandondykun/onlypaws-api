from django.apps import AppConfig


class ModerationAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.moderation_app"
    verbose_name = "Moderation"

    def ready(self):
        import apps.moderation_app.signals  # noqa: F401

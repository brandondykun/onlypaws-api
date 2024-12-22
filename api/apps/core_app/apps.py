from django.apps import AppConfig


class CoreAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core_app"

    def ready(self):
        import apps.core_app.signals

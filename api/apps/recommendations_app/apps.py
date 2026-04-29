from django.apps import AppConfig


class RecommendationsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recommendations_app"
    verbose_name = "Recommendations"

    def ready(self):
        import apps.recommendations_app.signals  # noqa: F401

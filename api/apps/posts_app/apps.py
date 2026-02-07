from django.apps import AppConfig


class PostsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts_app"

    def ready(self):
        # Import signals to register them
        import apps.posts_app.signals  # noqa: F401

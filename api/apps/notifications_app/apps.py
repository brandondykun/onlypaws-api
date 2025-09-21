from django.apps import AppConfig


class NotificationsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications_app'
    
    def ready(self):
        import apps.notifications_app.signals

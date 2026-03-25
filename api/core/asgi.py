"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Init telemetry AFTER Django setup so dictConfig(LOGGING) has already
# created the loggers — this lets init_telemetry attach the OTel handler
# to loggers with propagate=False (django.request, celery, apps, etc.).
from core.telemetry import init_telemetry
init_telemetry()

# Import websocket patterns AFTER Django initialization to avoid AppRegistryNotReady error
from apps.notifications_app.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})

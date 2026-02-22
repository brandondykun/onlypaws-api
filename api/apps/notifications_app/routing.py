from django.urls import re_path
from . import consumers

# ULID: 26 chars, Crockford Base32 (0-9, A-Z excluding I, L, O, U)
ULID_PATTERN = r'(?P<profile_public_id>[0-9A-HJ-NP-TV-Z]{26})'

websocket_urlpatterns = [
    re_path(r'^ws/notifications/' + ULID_PATTERN + r'/$', consumers.NotificationConsumer.as_asgi()),
]

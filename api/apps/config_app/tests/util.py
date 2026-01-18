"""
Test utilities for config app.
"""

from django.urls import reverse


ADS_CONFIG_URL = reverse("config_app:ads-config")
SYSTEM_STATUS_URL = reverse("config_app:system-status")
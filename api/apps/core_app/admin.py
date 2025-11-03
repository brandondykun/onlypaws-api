"""
Admin configuration for core_app.

Note: Most models are now registered in their respective apps:
- User models: user_app/admin.py
- Post models: posts_app/admin.py
- Interaction models: interactions_app/admin.py
- Moderation models: moderation_app/admin.py

This file is kept for backwards compatibility and any shared admin customization.
"""
from django.contrib import admin

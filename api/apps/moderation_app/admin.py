"""
Admin configuration for moderation app.
"""
from django.contrib import admin
from .models import ReportReason, PostReport

admin.site.register(ReportReason)
admin.site.register(PostReport)

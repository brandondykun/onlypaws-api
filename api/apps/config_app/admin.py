from django.contrib import admin
from .models import AppConfiguration
from unfold.admin import ModelAdmin


@admin.register(AppConfiguration)
class AppConfigurationAdmin(ModelAdmin):
    """Admin interface for AppConfiguration."""

    list_display = ["id", "key", "value", "updated_at", "created_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("key", "value", "description")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

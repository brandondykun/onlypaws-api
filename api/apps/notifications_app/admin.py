from django.contrib import admin
from .models import Notification
from unfold.admin import ModelAdmin


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "sender",
        "notification_type",
        "title",
        "is_read",
        "created_at",
    )
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "sender__username", "title", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("recipient", "sender", "post")
        )

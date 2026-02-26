"""
Admin configuration for moderation app.
"""

import json
from django.contrib import admin
from django.utils.html import format_html
from .models import ReportReason, PostReport, ProfileReportReason, ProfileReport, ProfanityLog

admin.site.register(ReportReason)
admin.site.register(PostReport)
admin.site.register(ProfileReportReason)
admin.site.register(ProfileReport)


@admin.register(ProfanityLog)
class ProfanityLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "truncated_text",
        "content_type",
        "detection_method",
        "profile_link",
        "created_at",
    ]
    list_filter = ["content_type", "detection_method", "created_at"]
    search_fields = ["original_text", "profile__username"]
    readonly_fields = [
        "original_text",
        "content_type",
        "detection_method",
        "formatted_detection_details",
        "profile",
        "created_at",
    ]
    list_per_page = 50
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def truncated_text(self, obj):
        text = obj.original_text
        return text[:80] + "..." if len(text) > 80 else text
    truncated_text.short_description = "Text"

    def profile_link(self, obj):
        if obj.profile:
            return format_html(
                '<a href="/admin/profile_app/profile/{}/change/">{}</a>',
                obj.profile.id,
                obj.profile.username,
            )
        return "-"
    profile_link.short_description = "Profile"

    def formatted_detection_details(self, obj):
        return format_html(
            "<pre>{}</pre>",
            json.dumps(obj.detection_details, indent=2),
        )
    formatted_detection_details.short_description = "Detection Details"

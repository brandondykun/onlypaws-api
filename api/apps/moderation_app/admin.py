"""
Admin configuration for moderation app.
"""

import json
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import (
    ReportReason,
    PostReport,
    ProfileReportReason,
    ProfileReport,
    ProfanityLog,
    Block,
    CustomBannedWord,
    WhitelistedWord,
)

admin.site.register(ReportReason)
admin.site.register(PostReport)
admin.site.register(ProfileReportReason)
admin.site.register(ProfileReport)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ["id", "blocker_username", "blocked_username", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["blocker__username", "blocked__username"]
    readonly_fields = ["blocker", "blocked", "created_at"]
    list_per_page = 50
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_select_related = ["blocker", "blocked"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def blocker_username(self, obj):
        return format_html(
            '<a href="/admin/profile_app/profile/{}/change/">{}</a>',
            obj.blocker.id,
            obj.blocker.username,
        )

    blocker_username.short_description = "Blocker"

    def blocked_username(self, obj):
        return format_html(
            '<a href="/admin/profile_app/profile/{}/change/">{}</a>',
            obj.blocked.id,
            obj.blocked.username,
        )

    blocked_username.short_description = "Blocked"


@admin.register(ProfanityLog)
class ProfanityLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "truncated_text",
        "matched_word_display",
        "content_type",
        "detection_method",
        "is_whitelisted",
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
    actions = ["whitelist_matched_words"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def truncated_text(self, obj):
        text = obj.original_text
        return text[:80] + "..." if len(text) > 80 else text

    truncated_text.short_description = "Text"

    def matched_word_display(self, obj):
        word = obj.detection_details.get("matched_word", "")
        return word or "-"

    matched_word_display.short_description = "Matched Word"

    def is_whitelisted(self, obj):
        word = obj.detection_details.get("matched_word", "")
        if not word:
            return False
        return WhitelistedWord.objects.filter(word=word).exists()

    is_whitelisted.short_description = "Whitelisted"
    is_whitelisted.boolean = True

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

    @admin.action(description="Whitelist matched word(s)")
    def whitelist_matched_words(self, request, queryset):
        created_words = []
        skipped_words = []
        no_word_count = 0

        for log in queryset:
            word = log.detection_details.get("matched_word", "").strip().lower()
            if not word:
                no_word_count += 1
                continue

            _, created = WhitelistedWord.objects.get_or_create(
                word=word,
                defaults={"notes": f"Whitelisted from ProfanityLog #{log.id}"},
            )
            if created:
                created_words.append(word)
            else:
                skipped_words.append(word)

        parts = []
        if created_words:
            parts.append(f"Whitelisted: {', '.join(created_words)}")
        if skipped_words:
            parts.append(f"Already whitelisted: {', '.join(set(skipped_words))}")
        if no_word_count:
            parts.append(
                f"{no_word_count} log(s) skipped (ML detection, no matched word)"
            )

        level = messages.SUCCESS if created_words else messages.INFO
        self.message_user(request, ". ".join(parts), level=level)


@admin.register(CustomBannedWord)
class CustomBannedWordAdmin(admin.ModelAdmin):
    list_display = ["word", "notes", "created_at"]
    search_fields = ["word"]


@admin.register(WhitelistedWord)
class WhitelistedWordAdmin(admin.ModelAdmin):
    list_display = ["word", "notes", "created_at"]
    search_fields = ["word"]

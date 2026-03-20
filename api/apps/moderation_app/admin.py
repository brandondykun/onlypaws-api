"""
Admin configuration for moderation app.
"""

import json
from django.contrib import admin, messages
from django.utils.html import format_html, mark_safe
from unfold.admin import ModelAdmin
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


@admin.register(ReportReason)
class ReportReasonAdmin(ModelAdmin):
    list_display = ["id", "name", "description", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]
    ordering = ["name"]


@admin.register(ProfileReportReason)
class ProfileReportReasonAdmin(ModelAdmin):
    list_display = ["id", "name", "description", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]
    ordering = ["name"]


@admin.register(PostReport)
class PostReportAdmin(ModelAdmin):
    list_display = [
        "id",
        "post",
        "reporter",
        "reason",
        "status",
        "created_at",
    ]
    list_filter = ["status", "reason", "created_at"]
    search_fields = ["details", "post__caption", "reporter__email"]
    readonly_fields = [
        "post",
        "reporter",
        "reason",
        "details",
        "created_at",
        "updated_at",
        "post_caption",
        "post_images",
    ]
    list_editable = ["status"]
    ordering = ["-created_at"]
    list_select_related = ["post", "reporter", "reason"]

    fieldsets = (
        ("Report Details", {"fields": ("post", "reporter", "reason", "details")}),
        (
            "Reported Post Content",
            {
                "fields": ("post_caption", "post_images"),
                "description": "Content from the reported post for review.",
            },
        ),
        (
            "Resolution",
            {"fields": ("status", "resolved_by", "resolution_note")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def post_caption(self, obj):
        return obj.post.caption if obj.post else "-"

    post_caption.short_description = "Post Caption"

    def post_images(self, obj):
        if not obj.post:
            return "-"
        images = obj.post.images.all()
        if not images:
            return "No images"
        html = ""
        for img in images:
            if img.image:
                html += format_html(
                    '<img src="{}" style="max-width:400px; max-height:400px;'
                    ' margin:5px; border:1px solid #ccc; border-radius:4px;" />',
                    img.image.url,
                )
        return mark_safe(html) if html else "No images"

    post_images.short_description = "Post Images"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resolved_by":
            kwargs["queryset"] = db_field.related_model.objects.filter(
                user__is_staff=True
            )
            user_profile = db_field.related_model.objects.filter(
                user=request.user
            ).first()
            if user_profile:
                kwargs["initial"] = user_profile.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProfileReport)
class ProfileReportAdmin(ModelAdmin):
    list_display = [
        "id",
        "profile",
        "reporter",
        "reason",
        "status",
        "created_at",
    ]
    list_filter = ["status", "reason", "created_at"]
    search_fields = ["details", "profile__username", "reporter__email"]
    readonly_fields = [
        "profile",
        "reporter",
        "reason",
        "details",
        "created_at",
        "updated_at",
        "profile_image_display",
        "profile_username",
        "profile_type",
        "profile_about",
        "profile_is_active",
        "profile_is_private",
        "profile_created_at",
        "profile_pet_details",
        "profile_business_details",
        "profile_post_images",
    ]
    list_editable = ["status"]
    ordering = ["-created_at"]
    list_select_related = ["profile", "reporter", "reason"]

    fieldsets = (
        ("Report Details", {"fields": ("profile", "reporter", "reason", "details")}),
        (
            "Reported Profile",
            {
                "fields": (
                    "profile_image_display",
                    "profile_username",
                    "profile_type",
                    "profile_about",
                    "profile_is_active",
                    "profile_is_private",
                    "profile_created_at",
                    "profile_pet_details",
                    "profile_business_details",
                ),
                "description": "Profile information for review.",
            },
        ),
        (
            "Profile Post Images",
            {
                "fields": ("profile_post_images",),
                "description": "Post images from the reported profile.",
            },
        ),
        (
            "Resolution",
            {"fields": ("status", "resolved_by", "resolution_note")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def profile_image_display(self, obj):
        if not obj.profile:
            return "-"
        try:
            profile_image = obj.profile.image
            if profile_image and profile_image.image:
                return format_html(
                    '<img src="{}" style="max-width:150px; max-height:150px;'
                    ' border-radius:50%; border:1px solid #ccc;" />',
                    profile_image.image.url,
                )
        except Exception:
            pass
        return "No profile image"

    profile_image_display.short_description = "Profile Image"

    def profile_username(self, obj):
        if not obj.profile:
            return "-"
        url = f"/admin/profile_app/profile/{obj.profile.id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.profile.username)

    profile_username.short_description = "Username"

    def profile_type(self, obj):
        if not obj.profile:
            return "-"
        return obj.profile.get_profile_type().capitalize()

    profile_type.short_description = "Profile Type"

    def profile_about(self, obj):
        if not obj.profile:
            return "-"
        specific = obj.profile.get_specific_profile()
        return getattr(specific, "about", "-") or "-"

    profile_about.short_description = "About"

    def profile_is_active(self, obj):
        return obj.profile.is_active if obj.profile else None

    profile_is_active.short_description = "Active"
    profile_is_active.boolean = True

    def profile_is_private(self, obj):
        return obj.profile.is_private if obj.profile else None

    profile_is_private.short_description = "Private"
    profile_is_private.boolean = True

    def profile_created_at(self, obj):
        return obj.profile.created_at if obj.profile else "-"

    profile_created_at.short_description = "Profile Created"

    def profile_pet_details(self, obj):
        if not obj.profile or not obj.profile.is_regular_profile():
            return "N/A — not a regular profile"
        rp = obj.profile.regularprofile
        parts = []
        if rp.name:
            parts.append(f"Name: {rp.name}")
        if rp.pet_type:
            parts.append(f"Pet type: {rp.pet_type.name}")
        if rp.breed:
            parts.append(f"Breed: {rp.breed}")
        return ", ".join(parts) if parts else "No pet details"

    profile_pet_details.short_description = "Pet Details"

    def profile_business_details(self, obj):
        if not obj.profile or not obj.profile.is_business_profile():
            return "N/A — not a business profile"
        bp = obj.profile.businessprofile
        parts = []
        if bp.business_name:
            parts.append(f"Business: {bp.business_name}")
        if bp.business_category:
            parts.append(f"Category: {bp.get_business_category_display()}")
        if bp.website:
            parts.append(
                format_html(
                    'Website: <a href="{}" target="_blank">{}</a>',
                    bp.website,
                    bp.website,
                )
            )
        if bp.phone:
            parts.append(f"Phone: {bp.phone}")
        if bp.verified:
            parts.append("Verified: Yes")
        return (
            format_html(", ".join(str(p) for p in parts))
            if parts
            else "No business details"
        )

    profile_business_details.short_description = "Business Details"

    def profile_post_images(self, obj):
        if not obj.profile:
            return "-"
        posts = obj.profile.posts.prefetch_related("images").order_by("-created_at")

        if not posts:
            return "No posts"
        html = ""
        for post in posts:
            for img in post.images.all():
                if img.image:
                    html += format_html(
                        '<a href="/admin/posts_app/post/{}/change/" title="{}">'
                        '<img src="{}" style="max-width:300px; max-height:300px;'
                        ' margin:5px; border:1px solid #ccc; border-radius:4px;" />'
                        "</a>",
                        post.id,
                        post.caption[:50] if post.caption else "",
                        img.image.url,
                    )
        if not html:
            return "No images in posts"
        return mark_safe(
            f'<div style="display:flex; flex-wrap:wrap; gap:5px;">{html}</div>'
        )

    profile_post_images.short_description = "Post Images"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resolved_by":
            kwargs["queryset"] = db_field.related_model.objects.filter(
                user__is_staff=True
            )
            user_profile = db_field.related_model.objects.filter(
                user=request.user
            ).first()
            if user_profile:
                kwargs["initial"] = user_profile.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Block)
class BlockAdmin(ModelAdmin):
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
class ProfanityLogAdmin(ModelAdmin):
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
class CustomBannedWordAdmin(ModelAdmin):
    list_display = ["id", "word", "notes", "created_at"]
    search_fields = ["word", "notes"]
    readonly_fields = ["created_at"]
    ordering = ["word"]


@admin.register(WhitelistedWord)
class WhitelistedWordAdmin(ModelAdmin):
    list_display = ["id", "word", "notes", "created_at"]
    search_fields = ["word", "notes"]
    readonly_fields = ["created_at"]
    ordering = ["word"]

"""
Admin configuration for posts app.
"""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import Post, PostImage, PostImageScaled, SavedPost, PostImageTag


# Inline for PostImageTag in PostImage admin
class PostImageTagInline(admin.TabularInline):
    model = PostImageTag
    extra = 0
    fields = [
        "tagged_profile",
        "tagged_by_profile",
        "x_position",
        "y_position",
        "created_at",
    ]
    readonly_fields = ["created_at"]
    ordering = ["id"]


# Inline for PostImageScaled in PostImage admin
class PostImageScaledInline(admin.TabularInline):
    model = PostImageScaled
    extra = 0
    fields = ["scale", "image", "width", "height", "created_at"]
    readonly_fields = ["image", "width", "height", "created_at"]
    ordering = ["scale"]


# Inline for PostImage in Post admin
class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    fields = ["image_preview", "image", "order"]
    readonly_fields = ["image", "image_preview"]
    ordering = ["order", "id"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:300px; max-height:300px;'
                ' border:1px solid #ccc; border-radius:4px;" />',
                obj.image.url,
            )
        return "-"

    image_preview.short_description = "Preview"


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "caption", "profile", "created_at", "contains_ai"]
    list_filter = ["contains_ai", "created_at"]
    search_fields = ["caption", "profile__username"]
    inlines = [PostImageInline]


@admin.register(PostImage)
class PostImageAdmin(ModelAdmin):
    list_display = ["id", "post", "order", "image"]
    list_filter = ["order", "created_at"]
    search_fields = ["post__id", "post__caption"]
    readonly_fields = ["image_preview", "post_aspect_ratio", "created_at"]
    inlines = [PostImageTagInline, PostImageScaledInline]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:400px; max-height:400px;'
                " border:1px solid #ccc; border-radius:4px; object-fit:cover;"
                ' aspect-ratio:{};" />',
                obj.image.url,
                obj.post.aspect_ratio.replace(":", "/"),
            )
        return "-"

    image_preview.short_description = "Preview"

    def post_aspect_ratio(self, obj):
        return obj.post.get_aspect_ratio_display()

    post_aspect_ratio.short_description = "Post Aspect Ratio"


@admin.register(PostImageScaled)
class PostImageScaledAdmin(ModelAdmin):
    list_display = [
        "id",
        "image",
        "post_image__post__id",
        "scale",
        "width",
        "height",
        "created_at",
    ]
    list_filter = ["scale", "created_at"]
    search_fields = ["image", "post_image__post__id", "post_image__post__caption"]
    ordering = ["image", "post_image", "scale"]
    readonly_fields = ["created_at"]


@admin.register(PostImageTag)
class PostImageTagAdmin(ModelAdmin):
    list_display = [
        "id",
        "post_image",
        "tagged_profile",
        "tagged_by_profile",
        "x_position",
        "y_position",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = [
        "tagged_profile__username",
        "tagged_by_profile__username",
        "post_image__post__id",
    ]
    readonly_fields = ["created_at"]


@admin.register(SavedPost)
class SavedPostAdmin(ModelAdmin):
    list_display = ["id", "profile", "post", "saved_at"]
    list_filter = ["saved_at"]
    search_fields = ["profile__username", "post__caption"]
    readonly_fields = ["saved_at"]
    ordering = ["-saved_at"]

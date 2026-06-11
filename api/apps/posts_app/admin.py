"""
Admin configuration for posts app.
"""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from apps.core_app.image_placeholders import blurhash_to_data_uri
from .models import Post, PostImage, PostImageScaled, SavedPost, PostImageTag

BLURHASH_PREVIEW_HEIGHT = 200
BLURHASH_PREVIEW_DECODE_HEIGHT = 64


def _dimensions_for_aspect_ratio(aspect_ratio, height):
    width_ratio, height_ratio = (int(value) for value in aspect_ratio.split(":"))
    width = round(height * width_ratio / height_ratio)
    return width, height


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
    list_display = [
        "id",
        "caption",
        "profile",
        "created_at",
        "contains_ai",
    ]
    list_filter = ["contains_ai", "created_at"]
    search_fields = ["caption", "profile__username"]
    inlines = [PostImageInline]


def _blurhash_preview(obj, aspect_ratio):
    """Render a decoded blurhash preview next to its raw string for admin."""
    if not obj.blurhash:
        return "-"

    preview_width, preview_height = _dimensions_for_aspect_ratio(
        aspect_ratio,
        BLURHASH_PREVIEW_HEIGHT,
    )
    decode_width, decode_height = _dimensions_for_aspect_ratio(
        aspect_ratio,
        BLURHASH_PREVIEW_DECODE_HEIGHT,
    )
    data_uri = blurhash_to_data_uri(
        obj.blurhash,
        width=decode_width,
        height=decode_height,
    )
    if not data_uri:
        return format_html("<code>{}</code>", obj.blurhash)

    return format_html(
        '<div style="display:flex; align-items:center; gap:12px;">'
        '<img src="{}" width="{}" height="{}" style="width:{}px; height:{}px;'
        " object-fit:cover; aspect-ratio:{}; flex:0 0 auto;"
        ' border:1px solid #ccc; border-radius:4px;" />'
        '<code style="word-break:break-all;">{}</code>'
        "</div>",
        data_uri,
        preview_width,
        preview_height,
        preview_width,
        preview_height,
        aspect_ratio.replace(":", "/"),
        obj.blurhash,
    )


@admin.register(PostImage)
class PostImageAdmin(ModelAdmin):
    list_display = ["id", "post", "order", "image"]
    list_filter = ["order", "created_at"]
    search_fields = ["post__id", "post__caption"]
    readonly_fields = ["image_preview", "post_aspect_ratio", "blurhash_preview", "blurhash", "created_at"]
    inlines = [PostImageTagInline, PostImageScaledInline]

    def blurhash_preview(self, obj):
        return _blurhash_preview(obj, obj.post.aspect_ratio)

    blurhash_preview.short_description = "BlurHash"

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

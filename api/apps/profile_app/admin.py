from django.contrib import admin
from django.utils.html import format_html, mark_safe
from unfold.admin import ModelAdmin
from .models import (
    Profile,
    RegularProfile,
    BusinessProfile,
    ProfileImage,
    ProfileImageScaled,
    PetType,
    Address,
)


@admin.register(PetType)
class PetTypeAdmin(ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ["id", "street_address", "city", "state", "country"]
    search_fields = ["street_address", "city", "state", "country"]
    list_filter = ["country", "state"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = [
        "id",
        "username",
        "user",
        "is_active",
        "is_private",
        "get_profile_type",
        "created_at",
        "public_id",
    ]
    search_fields = ["username", "user__email"]
    list_filter = ["is_active", "created_at"]
    readonly_fields = ["public_id", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_profile_type(self, obj):
        return obj.get_profile_type()

    get_profile_type.short_description = "Profile Type"


@admin.register(RegularProfile)
class RegularProfileAdmin(ModelAdmin):
    list_display = [
        "id",
        "public_id",
        "username",
        "name",
        "pet_type",
        "user_email",
        "created_at",
    ]
    search_fields = ["profile_ptr__username", "name", "profile_ptr__user__email"]
    list_filter = ["pet_type", "profile_ptr__created_at"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-profile_ptr__created_at"]

    def username(self, obj):
        return obj.profile_ptr.username

    def public_id(self, obj):
        return obj.profile_ptr.public_id

    public_id.short_description = "Public ID"

    def user_email(self, obj):
        return obj.profile_ptr.user.email

    user_email.short_description = "User Email"

    def created_at(self, obj):
        return obj.profile_ptr.created_at

    def updated_at(self, obj):
        return obj.profile_ptr.updated_at


@admin.register(BusinessProfile)
class BusinessProfileAdmin(ModelAdmin):
    list_display = [
        "id",
        "public_id",
        "username",
        "business_name",
        "business_category",
        "verified",
        "subscription_tier",
        "user_email",
        "created_at",
    ]
    search_fields = [
        "profile_ptr__username",
        "business_name",
        "profile_ptr__user__email",
    ]
    list_filter = [
        "business_category",
        "verified",
        "subscription_tier",
        "profile_ptr__created_at",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-profile_ptr__created_at"]

    def username(self, obj):
        return obj.profile_ptr.username

    def public_id(self, obj):
        return obj.profile_ptr.public_id

    public_id.short_description = "Public ID"

    def user_email(self, obj):
        return obj.profile_ptr.user.email

    user_email.short_description = "User Email"

    def created_at(self, obj):
        return obj.profile_ptr.created_at

    def updated_at(self, obj):
        return obj.profile_ptr.updated_at


@admin.register(ProfileImage)
class ProfileImageAdmin(ModelAdmin):
    list_display = [
        "id",
        "profile",
        "image",
        "processing_status",
        "created_at",
        "updated_at",
    ]
    search_fields = ["profile__username"]
    list_filter = ["processing_status"]
    readonly_fields = ["created_at", "updated_at", "image_preview", "scaled_previews"]
    ordering = ["-created_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:400px; max-height:400px;'
                ' border-radius:50%; border:1px solid #ccc;" />',
                obj.image.url,
            )
        return "-"

    image_preview.short_description = "Preview (Large — 400px)"

    def scaled_previews(self, obj):
        if not obj.pk:
            return "-"
        scaled = obj.scaled_images.all().order_by("-scale")
        if not scaled:
            return "No scaled versions"
        html = ""
        for s in scaled:
            if s.image:
                dim = ProfileImageScaled.SCALE_DIMENSIONS.get(s.scale, 200)
                html += format_html(
                    '<div style="display:inline-block; text-align:center; margin-right:20px;">'
                    '<div style="margin-bottom:5px; font-weight:bold;">{label} — {dim}px</div>'
                    '<img src="{url}" style="width:{dim}px; height:{dim}px;'
                    ' border-radius:50%; border:1px solid #ccc;" />'
                    "</div>",
                    label=s.get_scale_display(),
                    dim=dim,
                    url=s.image.url,
                )
        return mark_safe(html) if html else "No scaled versions"

    scaled_previews.short_description = "Scaled Versions"


@admin.register(ProfileImageScaled)
class ProfileImageScaledAdmin(ModelAdmin):
    list_display = [
        "id",
        "image",
        "profile_image__profile__username",
        "scale",
        "width",
        "height",
        "created_at",
    ]
    list_filter = ["scale"]
    search_fields = ["image", "profile_image__profile__username"]
    ordering = ["image", "profile_image", "scale"]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.image:
            dim = ProfileImageScaled.SCALE_DIMENSIONS.get(obj.scale, 200)
            return format_html(
                '<img src="{}" style="width:{}px; height:{}px;'
                ' border-radius:50%; border:1px solid #ccc;" />',
                obj.image.url,
                dim,
                dim,
            )
        return "-"

    image_preview.short_description = "Preview"

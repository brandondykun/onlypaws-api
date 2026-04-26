"""
Admin configuration for interactions app.
"""

from django.contrib import admin
from django.contrib.admin import widgets
from .models import Like, Comment, CommentLike, Follow, FollowRequest, PostInteraction
from unfold.admin import ModelAdmin


@admin.register(Like)
class LikeAdmin(ModelAdmin):
    list_display = ["id", "profile", "post", "liked_at"]
    list_filter = ["liked_at"]
    search_fields = ["profile__username", "post__caption"]
    readonly_fields = ["liked_at"]
    ordering = ["-liked_at"]


@admin.register(CommentLike)
class CommentLikeAdmin(ModelAdmin):
    list_display = ["id", "profile", "comment", "liked_at"]
    list_filter = ["liked_at"]
    search_fields = ["profile__username", "comment__text"]
    readonly_fields = ["liked_at"]
    ordering = ["-liked_at"]


@admin.register(Follow)
class FollowAdmin(ModelAdmin):
    list_display = ["id", "followed_by", "followed", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["followed__username", "followed_by__username"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(FollowRequest)
class FollowRequestAdmin(ModelAdmin):
    list_display = ["id", "requester", "target", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["requester__username", "target__username"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ["id", "profile", "post", "text", "created_at"]
    search_fields = ["text", "profile__username"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "text":
            kwargs["widget"] = widgets.AdminTextareaWidget(
                attrs={"style": "width: 86%;"}
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(PostInteraction)
class PostInteractionAdmin(ModelAdmin):
    list_display = [
        "id",
        "profile",
        "post",
        "interaction_type",
        "dwell_time_ms",
        "created_at",
    ]
    list_filter = ["interaction_type", "created_at"]
    search_fields = [
        "profile__username",
        "post__caption",
        "public_id",
    ]
    readonly_fields = ["public_id", "created_at"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_select_related = ("profile", "post")
    autocomplete_fields = ("profile", "post")

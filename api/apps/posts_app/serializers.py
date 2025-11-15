from rest_framework import serializers
from apps.posts_app.models import Post, PostImage, SavedPost
from django.db.models import Q
from apps.profile_app.serializers import ProfileSerializer
from drf_spectacular.utils import extend_schema_field

# Import interaction serializers from interactions_app
from apps.interactions_app.serializers import (
    LikeSerializer,
    CommentSerializer
)

# Import moderation serializers
from apps.moderation_app.serializers import PostReportPreviewSerializer


class PostImageSerializer(serializers.ModelSerializer):
    """Serializer for Post Images."""

    class Meta:
        model = PostImage
        fields = ["id", "post", "image", "order"]




class PostSerializer(serializers.ModelSerializer):
    """Serializer for Posts."""

    images = PostImageSerializer(many=True, read_only=True)
    likes = LikeSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "caption",
            "profile",
            "created_at",
            "updated_at",
            "images",
            "likes",
            "comments",
            "contains_ai",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "likes", "comments"]


class PostUpdateSerializer(serializers.ModelSerializer):
    """Minimal serializer for updating Posts (caption only)."""

    class Meta:
        model = Post
        fields = ["caption"]


class PostDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Posts."""

    images = serializers.SerializerMethodField()
    profile = ProfileSerializer()
    comments_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()
    is_hidden = serializers.SerializerMethodField()
    is_reported = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "caption",
            "profile",
            "created_at",
            "updated_at",
            "images",
            "comments_count",
            "likes_count",
            "liked",
            "is_saved",
            "reports",
            "is_hidden",
            "is_reported",
            "contains_ai",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "images",
            "comments_count",
            "likes_count",
            "liked",
            "is_saved",
            "reports",
            "is_hidden",
            "is_reported",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_images(self, obj):
        """Return post images (uses model's default ordering: order, then id)."""
        return PostImageSerializer(obj.images.all(), many=True, context=self.context).data

    def get_comments_count(self, obj) -> int:
        return obj.comments.count()

    def get_likes_count(self, obj) -> int:
        return obj.likes.count()

    def get_liked(self, obj) -> bool:
        # boolean - is requesting profile liked the post being fetched
        auth_profile_id = self.context["request"].headers["auth-profile-id"]
        if auth_profile_id:
            return obj.likes.filter(profile=auth_profile_id).exists()
        return False

    def get_is_saved(self, obj) -> bool:
        # boolean - did requesting profile save the post being fetched
        requesting_profile = self.context["request"].headers["auth-profile-id"]
        if requesting_profile:
            return obj.saved_by.filter(profile=requesting_profile).exists()
        return False

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_reports(self, obj):
        reports = obj.reports.filter(~Q(status="DISMISSED"))
        serializer = PostReportPreviewSerializer(reports, many=True)
        return serializer.data

    def get_is_hidden(self, obj) -> bool:
        return obj.reports.filter(~Q(status="DISMISSED")).count() > 0

    def get_is_reported(self, obj) -> bool:
        current_profile = self.context["request"].current_profile
        return obj.reports.filter(reporter=current_profile).exists()


class CreateSavedPostSerializer(serializers.ModelSerializer):
    """Serializer for creating saved Posts."""

    class Meta:
        model = SavedPost
        fields = ["id", "profile", "post"]

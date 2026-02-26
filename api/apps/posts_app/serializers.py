from decimal import Decimal
from rest_framework import serializers
from apps.posts_app.models import Post, PostImage, SavedPost, PostImageTag, PostImageScaled
from django.db.models import Q
from apps.profile_app.serializers import ProfileSerializer, SearchProfileSerializer
from apps.core_app.profanity_service import check_and_log_text
from drf_spectacular.utils import extend_schema_field

# Import interaction serializers from interactions_app
from apps.interactions_app.serializers import (
    LikeSerializer,
    CommentSerializer
)

# Import moderation serializers
from apps.moderation_app.serializers import PostReportPreviewSerializer


# ============================================================================
# Presigned Upload Serializers
# ============================================================================

class PrepareUploadRequestSerializer(serializers.Serializer):
    """Serializer for prepare-upload request."""
    
    image_count = serializers.IntegerField(min_value=1, max_value=10)


class UploadUrlSerializer(serializers.Serializer):
    """Serializer for individual upload URL details."""
    
    url = serializers.URLField()
    key = serializers.CharField()
    order = serializers.IntegerField()


class PrepareUploadResponseSerializer(serializers.Serializer):
    """Serializer for prepare-upload response."""

    post_id = serializers.IntegerField()
    post_public_id = serializers.CharField()
    upload_urls = UploadUrlSerializer(many=True)


class CompletePostSerializer(serializers.Serializer):
    """Serializer for completing a post after images are uploaded."""

    caption = serializers.CharField(max_length=1000)
    aspect_ratio = serializers.ChoiceField(choices=Post.AspectRatio.choices, default=Post.AspectRatio.SQUARE)
    ai_generated = serializers.BooleanField(default=False)
    tags = serializers.JSONField(required=False, allow_null=True)

    def validate_caption(self, value):
        profile = getattr(self.context.get("request"), "current_profile", None)
        profile_id = profile.id if profile else None
        if check_and_log_text(value, "CAPTION", profile_id=profile_id):
            raise serializers.ValidationError("That caption contains inappropriate language.")
        return value


# ============================================================================
# PostImageScaled Serializer
# ============================================================================

class PostImageScaledSerializer(serializers.ModelSerializer):
    """Serializer for scaled image variants."""

    public_id = serializers.SerializerMethodField()

    class Meta:
        model = PostImageScaled
        fields = ["id", "public_id", "scale", "image", "width", "height"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class PostImageTagSerializer(serializers.ModelSerializer):
    """Serializer for Post Image Tags."""

    tagged_profile = SearchProfileSerializer(read_only=True)
    tagged_by_profile = SearchProfileSerializer(read_only=True)
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = PostImageTag
        fields = ["id", "public_id", "tagged_profile", "tagged_by_profile", "x_position", "y_position", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class CreatePostImageTagSerializer(serializers.Serializer):
    """Serializer for creating a PostImageTag."""
    
    post_image_id = serializers.IntegerField(required=True)
    tagged_profile_id = serializers.IntegerField(required=True)
    x_position = serializers.DecimalField(max_digits=5, decimal_places=2, required=True, min_value=Decimal("0"), max_value=Decimal("100"))
    y_position = serializers.DecimalField(max_digits=5, decimal_places=2, required=True, min_value=Decimal("0"), max_value=Decimal("100"))
    original_width = serializers.IntegerField(required=True, min_value=1)
    original_height = serializers.IntegerField(required=True, min_value=1)

    def validate_post_image_id(self, value):
        """Validate that the post image exists."""
        if not PostImage.objects.filter(id=value).exists():
            raise serializers.ValidationError("Post image does not exist.")
        return value

    def validate_tagged_profile_id(self, value):
        """Validate that the profile exists."""
        from apps.profile_app.models import Profile
        if not Profile.objects.filter(id=value).exists():
            raise serializers.ValidationError("Profile does not exist.")
        return value


class PostImageSerializer(serializers.ModelSerializer):
    """Serializer for Post Images."""

    tags = PostImageTagSerializer(many=True, read_only=True)
    scaled_images = PostImageScaledSerializer(many=True, read_only=True)
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = PostImage
        fields = ["id", "public_id", "post", "image", "order", "tags", "scaled_images"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class PostSerializer(serializers.ModelSerializer):
    """Serializer for Posts."""

    images = PostImageSerializer(many=True, read_only=True)
    likes = LikeSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "public_id",
            "caption",
            "profile",
            "created_at",
            "updated_at",
            "images",
            "likes",
            "comments",
            "contains_ai",
            "aspect_ratio",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "likes", "comments"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class PostUpdateSerializer(serializers.ModelSerializer):
    """Minimal serializer for updating Posts (caption only)."""

    class Meta:
        model = Post
        fields = ["caption"]

    def validate_caption(self, value):
        profile = getattr(self.context.get("request"), "current_profile", None)
        profile_id = profile.id if profile else None
        if check_and_log_text(value, "CAPTION", profile_id=profile_id):
            raise serializers.ValidationError("That caption contains inappropriate language.")
        return value


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
    tagged_profiles = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "public_id",
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
            "aspect_ratio",
            "tagged_profiles",
            "status",
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
            "tagged_profiles",
            "status",
        ]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

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
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.likes.filter(profile=current_profile).exists()
        return False

    def get_is_saved(self, obj) -> bool:
        # boolean - did requesting profile save the post being fetched
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.saved_by.filter(profile=current_profile).exists()
        return False

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_reports(self, obj):
        reports = obj.reports.filter(~Q(status="DISMISSED"))
        serializer = PostReportPreviewSerializer(reports, many=True)
        return serializer.data

    def get_is_hidden(self, obj) -> bool:
        return obj.reports.filter(~Q(status="DISMISSED")).count() > 0

    def get_is_reported(self, obj) -> bool:
        user = self.context["request"].user
        return obj.reports.filter(reporter=user).exists()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_tagged_profiles(self, obj):
        """Return unique list of all profiles tagged across all post images."""
        # Collect all unique tagged profiles
        seen_profile_ids = set()
        tagged_profiles = []
        
        for image in obj.images.all():
            for tag in image.tags.all():
                if tag.tagged_profile_id not in seen_profile_ids:
                    seen_profile_ids.add(tag.tagged_profile_id)
                    tagged_profiles.append(tag.tagged_profile)
        
        # Get the current profile for the SearchProfileSerializer context
        current_profile = getattr(self.context["request"], "current_profile", None)
        profile_id = current_profile.id if current_profile else None

        return SearchProfileSerializer(
            tagged_profiles,
            many=True,
            context={"profile_id": profile_id, "request": self.context["request"]},
        ).data


class CreateSavedPostSerializer(serializers.ModelSerializer):
    """Serializer for creating saved Posts."""

    public_id = serializers.SerializerMethodField()

    class Meta:
        model = SavedPost
        fields = ["id", "public_id", "profile", "post"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

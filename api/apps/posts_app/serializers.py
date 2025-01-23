from rest_framework import serializers
from apps.core_app.models import (
    Post,
    PostImage,
    Like,
    Comment,
    Profile,
    Follow,
    CommentLike,
    SavedPost,
    ReportReason,
    PostReport,
)
from django.db.models import Q
from ..user_app.serializers import (
    ProfileSerializer,
    ProfileImageSerializer,
    PetTypeSerializer,
)


class PostImageSerializer(serializers.ModelSerializer):
    """Serializer for Post Images."""

    class Meta:
        model = PostImage
        fields = ["id", "post", "image"]


class LikeSerializer(serializers.ModelSerializer):
    """Serializer for Likes."""

    class Meta:
        model = Like
        fields = [
            "id",
            "post",
            "profile",
            "liked_at",
        ]
        read_only_fields = ["id", "liked_at"]


class CommentLikeSerializer(serializers.ModelSerializer):
    """Serializer for Comment Likes."""

    class Meta:
        model = CommentLike
        fields = [
            "id",
            "comment",
            "profile",
            "liked_at",
        ]
        read_only_fields = ["id", "liked_at"]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comments."""

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class CommentDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Comments."""

    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    parent_comment_username = serializers.SerializerMethodField()
    reply_to_comment_username = serializers.SerializerMethodField()

    profile = ProfileSerializer()

    class Meta:
        model = Comment
        fields = [
            "id",
            "text",
            "profile",
            "post",
            "created_at",
            "likes_count",
            "liked",
            "replies_count",
            "replies",
            "parent_comment_username",
            "reply_to_comment_username",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "likes_count",
            "liked",
            "replies_count",
            "replies",
            "parent_comment_username",
            "reply_to_comment_username",
        ]

    def get_likes_count(self, obj) -> bool:
        return obj.likes.count()

    def get_liked(self, obj) -> bool:
        # boolean - has requesting profile liked the comment being fetched
        auth_profile_id = self.context["request"].headers["auth-profile-id"]
        if auth_profile_id:
            return obj.likes.filter(profile=auth_profile_id).exists()
        return False

    def get_replies_count(self, obj) -> int:
        replies_count = obj.all_replies.count()
        return replies_count

    def get_replies(self, obj):
        return []

    def get_parent_comment_username(self, obj) -> str | None:
        if obj.parent_comment:
            return obj.parent_comment.profile.username
        return None

    def get_reply_to_comment_username(self, obj) -> str | None:
        if obj.reply_to_comment:
            return obj.reply_to_comment.profile.username
        return None


class FollowersSerializer(serializers.ModelSerializer):
    """Serializer for Followers."""

    followed_by = ProfileSerializer()

    class Meta:
        model = Follow
        fields = ["followed_by"]


class FollowingSerializer(serializers.ModelSerializer):
    """Serializer for Following."""

    followed = ProfileSerializer()

    class Meta:
        model = Follow
        fields = ["followed"]


class FollowSerializer(serializers.ModelSerializer):
    """Serializer for Follow."""

    class Meta:
        model = Follow
        fields = ["id", "followed", "followed_by", "created_at"]
        read_only_fields = ["id", "created_at"]


class FollowDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Follow."""

    followed = ProfileSerializer()
    followed_by = ProfileSerializer()

    class Meta:
        model = Follow
        fields = ["id", "followed", "followed_by", "created_at"]
        read_only_fields = ["id", "created_at"]


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
        ]
        read_only_fields = ["id", "created_at", "updated_at", "likes", "comments"]


class ReportReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReason
        fields = ["id", "name", "description"]


class PostReportPreviewSerializer(serializers.ModelSerializer):

    reason = ReportReasonSerializer()

    class Meta:
        model = PostReport
        fields = ["id", "reason", "status"]


class PostDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Posts."""

    images = PostImageSerializer(many=True, read_only=True)
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
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "comments_count",
            "likes_count",
            "liked",
            "is_saved",
            "reports",
            "is_hidden",
            "is_reported",
        ]

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

    def get_reports(self, obj):
        reports = obj.reports.filter(~Q(status="DISMISSED"))
        serializer = PostReportPreviewSerializer(reports, many=True)
        return serializer.data

    def get_is_hidden(self, obj) -> bool:
        return obj.reports.filter(~Q(status="DISMISSED")).count() > 0

    def get_is_reported(self, obj) -> bool:
        current_profile = self.context["request"].current_profile
        return obj.reports.filter(reporter=current_profile).exists()


class ProfileDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for Profile."""

    image = ProfileImageSerializer()
    is_following = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    pet_type = PetTypeSerializer()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "name",
            "about",
            "image",
            "is_following",
            "posts_count",
            "followers_count",
            "following_count",
            "breed",
            "pet_type",
        ]

    def get_is_following(self, obj) -> bool:
        # boolean - is requesting profile following the profile being fetched
        requesting_profile = self.context["request"].query_params.get("profileId", None)

        if requesting_profile:
            return obj.following.filter(followed_by=requesting_profile).exists()
        return False

    def get_posts_count(self, obj) -> int:
        requesting_profile = self.context["request"].query_params.get("profileId", None)
        posts = obj.posts.all()

        # if profile is fetching own posts, return all including reported inappropriate
        if str(obj.id) == str(requesting_profile):
            return posts.count()
        # filter posts that have been reported as inappropriate from count
        return posts.filter(~Q(reports__reason__id=1)).count()

    def get_followers_count(self, obj) -> int:
        followers = obj.following.all()
        return followers.count()

    def get_following_count(self, obj) -> int:
        following = obj.followers.all()
        return following.count()


class SearchProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profiles when a user searches for profiles.
    This adds the following attribute to the normal Profile serializer.
    """

    is_following = serializers.SerializerMethodField()
    image = ProfileImageSerializer()

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "is_following", "image"]

    def get_is_following(self, obj) -> bool:
        requesting_profile = self.context.get("profile_id")
        return obj.following.filter(followed_by=requesting_profile).exists()


class CreateSavedPostSerializer(serializers.ModelSerializer):
    """Serializer for creating saved Posts."""

    class Meta:
        model = SavedPost
        fields = ["id", "profile", "post"]


class CreatePostReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReport
        fields = ["post", "reason", "details"]

    def validate(self, data):
        # Check if user has already reported this post
        request = self.context.get("request")
        auth_profile_id = request.headers["auth-profile-id"]
        if PostReport.objects.filter(
            post=data["post"], reporter=auth_profile_id
        ).exists():
            raise serializers.ValidationError("You have already reported this post.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        # auth_profile_id = request.headers["auth-profile-id"]
        validated_data["reporter"] = request.current_profile
        return super().create(validated_data)


class PostReportDetailSerializer(serializers.ModelSerializer):
    reason = ReportReasonSerializer()
    reporter = serializers.StringRelatedField()

    class Meta:
        model = PostReport
        fields = [
            "id",
            "post",
            "reporter",
            "reason",
            "details",
            "status",
            "created_at",
            "resolution_note",
        ]

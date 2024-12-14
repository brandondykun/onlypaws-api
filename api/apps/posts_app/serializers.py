from rest_framework import serializers
from apps.core_app.models import (
    Post,
    PostImage,
    Like,
    Comment,
    Profile,
    Follow,
    CommentLike,
)
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
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

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        # boolean - has requesting profile liked the comment being fetched
        auth_profile_id = self.context["request"].headers["auth-profile-id"]
        if auth_profile_id:
            return obj.likes.filter(profile=auth_profile_id).exists()
        return False

    def get_replies_count(self, obj):
        replies_count = obj.all_replies.count()
        return replies_count

    def get_replies(self, obj):
        return []

    def get_parent_comment_username(self, obj):
        if obj.parent_comment:
            return obj.parent_comment.profile.username
        return None

    def get_reply_to_comment_username(self, obj):
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
        read_only_fields = ["id", "created_at", "updated_at"]


class PostDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Posts."""

    images = PostImageSerializer(many=True, read_only=True)
    profile = ProfileSerializer()
    comments_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()

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
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "comments_count",
            "likes_count",
            "liked",
        ]

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        # boolean - is requesting profile liked the post being fetched
        auth_profile_id = self.context["request"].headers["auth-profile-id"]
        if auth_profile_id:
            return obj.likes.filter(profile=auth_profile_id).exists()
        return False


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

    def get_is_following(self, obj):
        # boolean - is requesting profile following the profile being fetched
        requesting_profile = self.context["request"].query_params.get("profileId", None)
        if requesting_profile:
            return obj.following.filter(followed_by=requesting_profile).exists()
        return False

    def get_posts_count(self, obj):
        posts = obj.posts.all()
        return posts.count()

    def get_followers_count(self, obj):
        followers = obj.following.all()
        return followers.count()

    def get_following_count(self, obj):
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

    def get_is_following(self, obj):
        requesting_profile = self.context.get("profile_id")
        return obj.following.filter(followed_by=requesting_profile).exists()

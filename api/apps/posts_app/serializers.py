from rest_framework import serializers
from apps.core_app.models import Post, PostImage, Like, Comment, Profile, Follow
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from ..user_app.serializers import ProfileSerializer, ProfileImageSerializer


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


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comments."""

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class CommentDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Comments."""

    profile = ProfileSerializer()

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


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
    likes = LikeSerializer(many=True, read_only=True)
    comments = CommentDetailedSerializer(many=True, read_only=True)
    profile = ProfileSerializer()
    comments_count = serializers.SerializerMethodField()

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
            "comments_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "comments_count"]

    def get_comments_count(self, obj):
        return obj.comments.count()


class ProfileDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for Profile."""

    posts = PostSerializer(many=True)
    followers = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    image = ProfileImageSerializer()
    is_following = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "about",
            "followers",
            "following",
            "posts",
            "image",
            "is_following",
            "posts_count",
        ]

    def get_followers(self, obj):
        followers = obj.following.all()
        serializer = FollowersSerializer(
            followers, many=True, context={"request": self.context["request"]}
        )
        data = [item["followed_by"] for item in serializer.data]
        return data

    def get_following(self, obj):
        following = obj.followers.all()
        serializer = FollowingSerializer(
            following, many=True, context={"request": self.context["request"]}
        )
        data = [item["followed"] for item in serializer.data]
        return data

    def get_is_following(self, obj):
        requesting_profile = self.context.get("request").user.profile
        return obj.following.filter(followed_by=requesting_profile).exists()

    def get_posts_count(self, obj):
        posts = obj.posts.all()
        return posts.count()


class SearchProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profiles when a user searches for profiles.
    This adds the following attribute to the normal Profile serializer.
    """

    is_following = serializers.SerializerMethodField()
    image = ProfileImageSerializer()

    class Meta:
        model = Profile
        fields = ["id", "username", "about", "user", "is_following", "image"]

    def get_is_following(self, obj):
        requesting_profile = self.context.get("request").user.profile
        return obj.following.filter(followed_by=requesting_profile).exists()

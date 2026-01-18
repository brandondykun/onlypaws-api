"""
Serializers for the admin dashboard app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from typing import Literal
from apps.profile_app.models import Profile
from apps.profile_app.serializers import ProfileImageSerializer, PetTypeSerializer
from apps.announcements_app.models import Announcement
from apps.moderation_app.models import ReportReason

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for User objects in admin context."""

    profiles_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_active",
            "is_staff",
            "is_email_verified",
            "regular_profile_onboarding_completed",
            "business_profile_onboarding_completed",
            "profiles_count",
        ]

    def get_profiles_count(self, obj) -> int:
        return obj.profiles.count()


class AdminUserProfileSerializer(serializers.ModelSerializer):
    """Minimal profile serializer for embedding in user detail response."""

    image = ProfileImageSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "is_active",
            "created_at",
            "image",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> str:
        return obj.get_profile_type()


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for User objects in admin context.
    Includes all user fields except password, plus their profiles.
    """

    profiles = AdminUserProfileSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "regular_profile_onboarding_completed",
            "business_profile_onboarding_completed",
            "last_login",
            "profiles",
        ]


class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile objects in admin context."""

    image = ProfileImageSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "user",
            "user_email",
            "is_active",
            "created_at",
            "updated_at",
            "image",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> str:
        return obj.get_profile_type()


class AdminProfileDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Profile objects in admin context.
    Includes user info, profile stats, and type-specific fields.
    """

    image = ProfileImageSerializer(read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    profile_type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    breed = serializers.SerializerMethodField()
    pet_type = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "user_id",
            "user_email",
            "name",
            "about",
            "breed",
            "pet_type",
            "image",
            "is_active",
            "created_at",
            "updated_at",
            "posts_count",
            "followers_count",
            "following_count",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

    def get_name(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, 'regularprofile'):
            return obj.regularprofile.name
        elif hasattr(obj, 'businessprofile'):
            return obj.businessprofile.business_name
        return ""

    def get_about(self, obj):
        """Get about from the specific profile type."""
        if hasattr(obj, 'regularprofile'):
            return obj.regularprofile.about
        elif hasattr(obj, 'businessprofile'):
            return obj.businessprofile.about
        return ""

    def get_breed(self, obj):
        """Get breed from RegularProfile."""
        if hasattr(obj, 'regularprofile'):
            return obj.regularprofile.breed
        return ""

    def get_pet_type(self, obj):
        """Get pet_type from RegularProfile."""
        if hasattr(obj, 'regularprofile') and obj.regularprofile.pet_type:
            return PetTypeSerializer(obj.regularprofile.pet_type).data
        return None

    def get_posts_count(self, obj) -> int:
        """Get count of all posts for this profile."""
        return obj.posts.count()

    def get_followers_count(self, obj) -> int:
        """Get count of followers."""
        return obj.following.count()

    def get_following_count(self, obj) -> int:
        """Get count of profiles this profile is following."""
        return obj.followers.count()


class AdminAnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement objects in admin list context."""

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "priority",
            "announcement_type",
            "is_active",
            "start_date",
            "end_date",
            "created_at",
        ]


class AdminAnnouncementDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Announcement objects in admin context.
    Used for retrieve, create, and update operations.
    """

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "message",
            "priority",
            "announcement_type",
            "is_active",
            "start_date",
            "end_date",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AdminReportReasonSerializer(serializers.ModelSerializer):
    """Serializer for ReportReason objects in admin list context."""

    class Meta:
        model = ReportReason
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
        ]


class AdminReportReasonDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for ReportReason objects in admin context.
    Used for retrieve, create, and update operations.
    """

    class Meta:
        model = ReportReason
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


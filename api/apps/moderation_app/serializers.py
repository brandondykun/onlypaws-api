"""
Serializers for the moderation app.
"""

from rest_framework import serializers
from apps.moderation_app.models import (
    ReportReason,
    PostReport,
    ProfileReportReason,
    ProfileReport,
    Block,
)
from apps.profile_app.models import Profile


class ReportReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReason
        fields = ["id", "name", "description"]


class PostReportPreviewSerializer(serializers.ModelSerializer):

    reason = ReportReasonSerializer()

    class Meta:
        model = PostReport
        fields = ["id", "reason", "status", "created_at", "updated_at", "details"]


class CreatePostReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReport
        fields = ["post", "reason", "details"]

    def validate(self, data):
        # Check if user has already reported this post
        request = self.context.get("request")
        user = request.user
        if PostReport.objects.filter(post=data["post"], reporter=user).exists():
            raise serializers.ValidationError("You have already reported this post.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["reporter"] = request.user
        return super().create(validated_data)


class PostReportDetailSerializer(serializers.ModelSerializer):
    reason = ReportReasonSerializer()
    reporter = serializers.StringRelatedField()
    post_profile_username = serializers.CharField(
        source="post.profile.username", read_only=True
    )
    post_public_id = serializers.CharField(source="post.public_id", read_only=True)

    class Meta:
        model = PostReport
        fields = [
            "id",
            "post",
            "post_public_id",
            "post_profile_username",
            "reporter",
            "reason",
            "details",
            "status",
            "created_at",
            "resolution_note",
        ]


class ProfileReportReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileReportReason
        fields = ["id", "name", "description"]


class CreateProfileReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileReport
        fields = ["profile", "reason", "details"]

    def validate(self, data):
        request = self.context.get("request")
        user = request.user
        # Prevent self-reporting (can't report any profile owned by the user)
        if data["profile"].user == user:
            raise serializers.ValidationError("You cannot report your own profile.")
        # Check if user has already reported this profile
        if ProfileReport.objects.filter(
            profile=data["profile"], reporter=user
        ).exists():
            raise serializers.ValidationError("You have already reported this profile.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["reporter"] = request.user
        return super().create(validated_data)


class ProfileReportDetailSerializer(serializers.ModelSerializer):
    reason = ProfileReportReasonSerializer()
    reporter = serializers.StringRelatedField()
    profile_username = serializers.CharField(source="profile.username", read_only=True)

    class Meta:
        model = ProfileReport
        fields = [
            "id",
            "profile",
            "profile_username",
            "reporter",
            "reason",
            "details",
            "status",
            "created_at",
            "updated_at",
            "resolution_note",
        ]


class CreateBlockSerializer(serializers.Serializer):
    profile_id = serializers.CharField(help_text="Public ID of the profile to block.")

    def validate_profile_id(self, value):
        try:
            profile = Profile.objects.get(public_id=value)
        except Profile.DoesNotExist:
            raise serializers.ValidationError("Profile not found.")
        return profile

    def validate(self, data):
        request = self.context.get("request")
        current_profile = request.current_profile
        target_profile = data["profile_id"]
        if current_profile.id == target_profile.id:
            raise serializers.ValidationError("You cannot block yourself.")
        if Block.objects.filter(
            blocker=current_profile, blocked=target_profile
        ).exists():
            raise serializers.ValidationError("You have already blocked this profile.")
        return data


class BlockSerializer(serializers.ModelSerializer):
    blocked_public_id = serializers.CharField(
        source="blocked.public_id", read_only=True
    )
    blocked_username = serializers.CharField(source="blocked.username", read_only=True)

    class Meta:
        model = Block
        fields = ["id", "blocked_public_id", "blocked_username", "created_at"]


class BlockedProfileSerializer(serializers.ModelSerializer):
    """Serializer for listing blocked profiles with basic profile info."""

    blocked_profile = serializers.SerializerMethodField()

    class Meta:
        model = Block
        fields = ["id", "blocked_profile", "created_at"]

    def get_blocked_profile(self, obj):
        from apps.profile_app.serializers import ProfileSerializer
        return ProfileSerializer(obj.blocked, context=self.context).data

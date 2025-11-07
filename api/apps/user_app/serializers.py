"""
Serializers for the User API view.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.user_app.models import (
    VerifyEmailToken,
    ResetPasswordToken,
)
from apps.profile_app.serializers import ProfileOptionSerializer
from django.contrib.auth.password_validation import validate_password


# ============================================================================
# User Serializers
# ============================================================================

class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User object."""

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "password", "is_email_verified"]
        extra_kwargs = {"password": {"write_only": True, "min_length": 9}}
        read_only_fields = ["is_email_verified"]

    def create(self, validated_data):
        """Create and return a user with encrypted password."""
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        """Update and return user."""
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user


# ============================================================================
# User and Profile Integration Serializers
# ============================================================================

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user and their profiles."""

    profiles = ProfileOptionSerializer(many=True, read_only=True)

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "profiles", "is_email_verified"]
        read_only_fields = ["is_email_verified"]


# ============================================================================
# Authentication & Token Serializers
# ============================================================================

class VerifyEmailTokenSerializer(serializers.ModelSerializer):
    """Serializer for VerifyEmailToken."""

    class Meta:
        model = VerifyEmailToken
        fields = ["id", "user", "token", "created_at"]
        read_only_fields = ["created_at"]


class ResetPasswordTokenSerializer(serializers.ModelSerializer):
    """Serializer for ResetPasswordToken."""

    class Meta:
        model = ResetPasswordToken
        fields = ["id", "user", "token", "created_at"]
        read_only_fields = ["created_at"]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=9)

    def validate_new_password(self, value):
        """Validate the new password."""
        # Use Django's built-in password validation
        validate_password(value)
        return value


class RequestEmailChangeSerializer(serializers.Serializer):
    """Serializer for email change request."""

    email = serializers.EmailField(required=True)


class VerifyEmailChangeSerializer(serializers.Serializer):
    """Serializer for email change verification."""

    token = serializers.CharField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset."""

    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, min_length=9)

    def validate_password(self, value):
        """Validate the password."""
        validate_password(value)
        return value

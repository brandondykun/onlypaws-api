"""
Serializers for the User API view.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.core_app.models import (
    Profile,
    ProfileImage,
    PetType,
    VerifyEmailToken,
    ResetPasswordToken,
)


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


class ProfileImageSerializer(serializers.ModelSerializer):
    """Serializer for profile image."""

    class Meta:
        model = ProfileImage
        fields = ["id", "profile", "image", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class PetTypeSerializer(serializers.ModelSerializer):
    """Serializer for pet type."""

    class Meta:
        model = PetType
        fields = ["id", "name"]


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profiles."""

    image = ProfileImageSerializer()
    pet_type = PetTypeSerializer()

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "image", "breed", "pet_type"]
        read_only_fields = ["id", "image"]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Profiles."""

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "image", "breed", "pet_type"]
        read_only_fields = ["id", "image"]


class ProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for Creating a Profile."""

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "user", "breed", "pet_type"]


class ProfileDetailedSerializer(serializers.ModelSerializer):
    """Serializer for Profiles."""

    user = UserSerializer()
    image = ProfileImageSerializer()
    pet_type = PetTypeSerializer()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "name",
            "about",
            "user",
            "image",
            "breed",
            "pet_type",
        ]


class ProfileOptionSerializer(serializers.ModelSerializer):
    """Serializer for Profile option."""

    class Meta:
        model = Profile
        fields = ["id", "username"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user and profile."""

    profiles = ProfileOptionSerializer(many=True)

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "profiles", "is_email_verified"]
        read_only_fields = ["is_email_verified"]


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

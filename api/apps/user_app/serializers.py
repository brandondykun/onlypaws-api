"""
Serializers for the User API view.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.core_app.models import Profile, ProfileImage


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User object."""

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "password"]
        extra_kwargs = {"password": {"write_only": True, "min_length": 5}}

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


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profiles."""

    image = ProfileImageSerializer()

    class Meta:
        model = Profile
        fields = ["id", "username", "about", "user", "image"]
        read_only_fields = ["image"]


class ProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for Creating a Profile."""

    class Meta:
        model = Profile
        fields = ["id", "username", "about", "user"]


class ProfileDetailedSerializer(serializers.ModelSerializer):
    """Serializer for Profiles."""

    user = UserSerializer()
    image = ProfileImageSerializer()

    class Meta:
        model = Profile
        fields = ["id", "username", "about", "user", "image"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user and profile."""

    profile = ProfileDetailedSerializer()

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "profile"]

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
from django.contrib.auth.password_validation import validate_password
from typing import Literal
from django.db.models import Q

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
    profile_type = serializers.SerializerMethodField()
    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "image", "breed", "pet_type", "profile_type"]
        read_only_fields = ["id", "image", "profile_type"]
    
    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Profiles."""

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "image", "breed", "pet_type"]
        read_only_fields = ["id", "image"]
    
    def update(self, instance, validated_data):
        """Update both Profile legacy fields and RegularProfile _new fields."""
        from django.db import connection
        
        # Update the base Profile (legacy fields)
        profile = super().update(instance, validated_data)
        
        # Update RegularProfile _new fields if it exists
        if hasattr(profile, 'regularprofile'):
            # Build update query dynamically based on what fields are being updated
            update_fields = []
            params = []
            
            if 'name' in validated_data:
                update_fields.append("name_new = %s")
                params.append(validated_data['name'])
            
            if 'about' in validated_data:
                update_fields.append("about_new = %s")
                params.append(validated_data['about'])
            
            if 'breed' in validated_data:
                update_fields.append("breed_new = %s")
                params.append(validated_data['breed'])
            
            if 'pet_type' in validated_data:
                update_fields.append("pet_type_new_id = %s")
                pet_type = validated_data['pet_type']
                params.append(pet_type.id if pet_type else None)
            
            # Only run update if there are fields to update
            if update_fields:
                params.append(profile.id)
                with connection.cursor() as cursor:
                    query = f"""
                        UPDATE core_app_regularprofile 
                        SET {', '.join(update_fields)}
                        WHERE profile_ptr_id = %s
                    """
                    cursor.execute(query, params)
        
        return profile


class ProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for Creating a Profile."""

    class Meta:
        model = Profile
        fields = ["id", "username", "name", "about", "user", "breed", "pet_type"]
    
    def create(self, validated_data):
        """Create Profile and RegularProfile, maintaining data in both."""
        from apps.core_app.models import RegularProfile
        from django.db import connection
        
        # Extract fields
        name = validated_data.get('name', '')
        about = validated_data.get('about', '')
        breed = validated_data.get('breed', '')
        pet_type = validated_data.get('pet_type', None)
        
        # Create the base Profile with legacy fields
        profile = Profile.objects.create(**validated_data)
        
        # Create RegularProfile using raw SQL to avoid ORM issues
        with connection.cursor() as cursor:
            pet_type_id = pet_type.id if pet_type else None
            cursor.execute(
                """
                INSERT INTO core_app_regularprofile 
                    (profile_ptr_id, about_new, name_new, pet_type_new_id, breed_new)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [profile.id, about, name, pet_type_id, breed]
            )
        
        return profile


class ProfileOptionSerializer(serializers.ModelSerializer):
    """Serializer for Profile option."""

    image = ProfileImageSerializer()
    profile_type = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["id", "username", "image", "name", "profile_type"]
        read_only_fields = ["profile_type"]
    
    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()


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


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=9)

    def validate_new_password(self, value):
        """Validate the new password."""
        # Use Django's built-in password validation
        validate_password(value)
        return value


class ProfileDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Profile."""

    image = ProfileImageSerializer()
    is_following = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    pet_type = PetTypeSerializer()
    profile_type = serializers.SerializerMethodField()

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
            "profile_type"
        ]
    
    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

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


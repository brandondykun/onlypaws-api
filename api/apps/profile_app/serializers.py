"""
Serializers for the Profile API.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.profile_app.models import (
    Profile,
    RegularProfile,
    BusinessProfile,
    Address,
    ProfileImage,
    ProfileImageScaled,
    PetType,
)
from apps.interactions_app.models import FollowRequest
from apps.core_app.profanity_service import check_and_log_username, check_and_log_text
from typing import Literal
from django.db.models import Q


def _validate_profanity(value, field_label="text", content_type="USERNAME", profile_id=None):
    """Shared profanity validation for short text fields."""
    if check_and_log_username(value, content_type, profile_id=profile_id):
        raise serializers.ValidationError(f"That {field_label} is not allowed.")
    return value


def _validate_username_profanity(value, profile_id=None):
    """Shared username profanity validation for profile serializers."""
    return _validate_profanity(value, "username", "USERNAME", profile_id=profile_id)


def _validate_text_profanity(value, field_label="text", content_type="ABOUT", profile_id=None):
    """Shared profanity validation for longer-form text fields."""
    if check_and_log_text(value, content_type, profile_id=profile_id):
        raise serializers.ValidationError(
            f"That {field_label} contains inappropriate language."
        )
    return value


# ============================================================================
# Supporting Model Serializers
# ============================================================================


class ProfileImageScaledSerializer(serializers.ModelSerializer):
    """Serializer for scaled profile image variants."""

    public_id = serializers.SerializerMethodField()

    class Meta:
        model = ProfileImageScaled
        fields = ["id", "public_id", "scale", "image", "width", "height"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class ProfileImageSerializer(serializers.ModelSerializer):
    """Serializer for profile image. Includes scaled variants when present."""

    scaled_images = ProfileImageScaledSerializer(many=True, read_only=True)
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = ProfileImage
        fields = [
            "id",
            "public_id",
            "profile",
            "image",
            "processing_status",
            "created_at",
            "updated_at",
            "scaled_images",
        ]
        read_only_fields = ["created_at", "updated_at", "processing_status"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


# ============================================================================
# Presigned profile image upload serializers
# ============================================================================


class ProfileImageUploadUrlRequestSerializer(serializers.Serializer):
    """Request body for requesting a presigned upload URL."""

    profile_id = serializers.IntegerField(min_value=1)


class ProfileImageUploadUrlResponseSerializer(serializers.Serializer):
    """Response with presigned URL and key for frontend upload."""

    upload_url = serializers.URLField()
    key = serializers.CharField()
    expires_in = serializers.IntegerField(required=False)


class ConfirmProfileImageUploadRequestSerializer(serializers.Serializer):
    """Request body for confirming upload after frontend PUT to presigned URL."""

    profile_id = serializers.IntegerField(min_value=1)
    key = serializers.CharField()


class PetTypeSerializer(serializers.ModelSerializer):
    """Serializer for pet type."""

    public_id = serializers.SerializerMethodField()

    class Meta:
        model = PetType
        fields = ["id", "public_id", "name"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address."""

    public_id = serializers.SerializerMethodField()

    class Meta:
        model = Address
        fields = [
            "id",
            "public_id",
            "street_address",
            "street_address_2",
            "city",
            "state",
            "postal_code",
            "country",
            "full_address_text",
        ]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None


# ============================================================================
# Follow Serializers - Now in interactions_app
# ============================================================================
# Follow serializers have been moved to apps.interactions_app.serializers
# Import them from there if needed:
# from apps.interactions_app.serializers import (
#     CreateFollowSerializer,
#     FollowSerializer,
# )


# ============================================================================
# Regular Profile Serializers
# ============================================================================


class RegularProfileSerializer(serializers.ModelSerializer):
    """Serializer for Regular (Pet) Profiles - Read operations."""

    image = serializers.SerializerMethodField()
    pet_type = PetTypeSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    username = serializers.CharField(source="profile_ptr.username", read_only=True)
    user = serializers.PrimaryKeyRelatedField(source="profile_ptr.user", read_only=True)
    is_active = serializers.BooleanField(source="profile_ptr.is_active", read_only=True)
    is_private = serializers.BooleanField(
        source="profile_ptr.is_private", read_only=True
    )
    created_at = serializers.DateTimeField(
        source="profile_ptr.created_at", read_only=True
    )
    updated_at = serializers.DateTimeField(
        source="profile_ptr.updated_at", read_only=True
    )

    class Meta:
        model = RegularProfile
        fields = [
            "id",
            "public_id",
            "username",
            "user",
            "name",
            "about",
            "breed",
            "pet_type",
            "image",
            "is_active",
            "is_private",
            "created_at",
            "updated_at",
            "profile_type",
        ]
        read_only_fields = [
            "id",
            "username",
            "user",
            "image",
            "is_active",
            "is_private",
            "created_at",
            "updated_at",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["regular"]:
        return "regular"

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_image(self, obj):
        """Get image from the parent Profile."""
        if hasattr(obj.profile_ptr, "image"):
            return ProfileImageSerializer(obj.profile_ptr.image).data
        return None


class RegularProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Regular (Pet) Profiles."""

    username = serializers.CharField()
    user = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())
    name = serializers.CharField(required=False, allow_blank=True, default="")
    about = serializers.CharField(required=False, allow_blank=True, default="")
    breed = serializers.CharField(required=False, allow_blank=True, default="")
    pet_type = serializers.PrimaryKeyRelatedField(
        queryset=PetType.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = RegularProfile
        fields = [
            "id",
            "public_id",
            "username",
            "user",
            "name",
            "about",
            "breed",
            "pet_type",
        ]
        read_only_fields = ["id", "public_id"]

    def create(self, validated_data):
        """Create RegularProfile (which also creates the base Profile)."""
        # Extract parent Profile fields
        username = validated_data.pop("username")
        user = validated_data.pop("user")

        # Create RegularProfile (automatically creates Profile via multi-table inheritance)
        regular_profile = RegularProfile.objects.create(
            username=username, user=user, **validated_data
        )

        return regular_profile

    def to_representation(self, instance):
        """Use the read serializer for output."""
        return RegularProfileSerializer(instance).data


class RegularProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Regular (Pet) Profiles."""

    username = serializers.CharField(required=False)
    name = serializers.CharField(required=False, allow_blank=True)
    about = serializers.CharField(required=False, allow_blank=True)
    breed = serializers.CharField(required=False, allow_blank=True)
    is_private = serializers.BooleanField(required=False)
    pet_type = serializers.PrimaryKeyRelatedField(
        queryset=PetType.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = RegularProfile
        fields = ["username", "name", "about", "breed", "pet_type", "is_private"]

    def update(self, instance, validated_data):
        """Update RegularProfile and parent Profile fields."""
        # Update parent Profile fields if provided
        if "username" in validated_data:
            instance.profile_ptr.username = validated_data.pop("username")
        if "is_private" in validated_data:
            instance.profile_ptr.is_private = validated_data.pop("is_private")

        # Save parent if any parent fields were updated
        if "username" in self.initial_data or "is_private" in self.initial_data:
            instance.profile_ptr.save()
            # Refresh to prevent child save from overwriting parent with cached values
            instance.refresh_from_db()

        # Update RegularProfile fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        return instance

    def to_representation(self, instance):
        """Use the read serializer for output."""
        return RegularProfileSerializer(instance).data


class RegularProfileDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Regular Profiles (includes counts and relationships)."""

    image = serializers.SerializerMethodField()
    pet_type = PetTypeSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    username = serializers.CharField(source="profile_ptr.username", read_only=True)
    is_private = serializers.BooleanField(
        source="profile_ptr.is_private", read_only=True
    )
    is_following = serializers.SerializerMethodField()
    follows_you = serializers.SerializerMethodField()
    has_requested_follow = serializers.SerializerMethodField()
    can_view_posts = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = RegularProfile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "about",
            "breed",
            "pet_type",
            "image",
            "is_private",
            "is_following",
            "follows_you",
            "has_requested_follow",
            "can_view_posts",
            "posts_count",
            "followers_count",
            "following_count",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["regular"]:
        return "regular"

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_image(self, obj):
        """Get image from the parent Profile."""
        if hasattr(obj.profile_ptr, "image"):
            return ProfileImageSerializer(obj.profile_ptr.image).data
        return None

    def get_is_following(self, obj) -> bool:
        """Check if requesting profile is following this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.profile_ptr.following.filter(
                followed_by=current_profile
            ).exists()
        return False

    def get_follows_you(self, obj) -> bool:
        """Check if this profile is following the requesting profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.profile_ptr.followers.filter(followed=current_profile).exists()
        return False

    def get_has_requested_follow(self, obj) -> bool:
        """Check if requesting profile has a pending follow request to this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return FollowRequest.objects.filter(
                requester=current_profile, target=obj.profile_ptr
            ).exists()
        return False

    def get_can_view_posts(self, obj) -> bool:
        """Check if requesting profile can view this profile's posts."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        # Can always view own posts
        if current_profile and obj.profile_ptr == current_profile:
            return True
        # Public profiles are visible to all
        if not obj.profile_ptr.is_private:
            return True
        # Private profiles require following
        if current_profile:
            return obj.profile_ptr.following.filter(
                followed_by=current_profile
            ).exists()
        return False

    def get_posts_count(self, obj) -> int:
        """Get count of posts for this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        posts = obj.profile_ptr.posts.all()

        # if profile is fetching own posts, return all including reported inappropriate
        if current_profile and obj.profile_ptr == current_profile:
            return posts.count()
        # filter posts that have been reported as inappropriate from count
        return posts.filter(~Q(reports__reason__id=1)).count()

    def get_followers_count(self, obj) -> int:
        """Get count of followers."""
        return obj.profile_ptr.following.count()

    def get_following_count(self, obj) -> int:
        """Get count of profiles this profile is following."""
        return obj.profile_ptr.followers.count()


# ============================================================================
# Business Profile Serializers
# ============================================================================


class BusinessProfileSerializer(serializers.ModelSerializer):
    """Serializer for Business Profiles - Read operations."""

    image = serializers.SerializerMethodField()
    address = AddressSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    username = serializers.CharField(source="profile_ptr.username", read_only=True)
    user = serializers.PrimaryKeyRelatedField(source="profile_ptr.user", read_only=True)
    is_active = serializers.BooleanField(source="profile_ptr.is_active", read_only=True)
    is_private = serializers.BooleanField(
        source="profile_ptr.is_private", read_only=True
    )
    created_at = serializers.DateTimeField(
        source="profile_ptr.created_at", read_only=True
    )
    updated_at = serializers.DateTimeField(
        source="profile_ptr.updated_at", read_only=True
    )

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "public_id",
            "username",
            "user",
            "business_name",
            "business_category",
            "about",
            "website",
            "phone",
            "address",
            "verified",
            "subscription_tier",
            "analytics_enabled",
            "business_hours",
            "image",
            "is_active",
            "is_private",
            "created_at",
            "updated_at",
            "profile_type",
        ]
        read_only_fields = [
            "id",
            "username",
            "user",
            "image",
            "verified",
            "subscription_tier",
            "analytics_enabled",
            "is_active",
            "is_private",
            "created_at",
            "updated_at",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["business"]:
        return "business"

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_image(self, obj):
        """Get image from the parent Profile."""
        if hasattr(obj.profile_ptr, "image"):
            return ProfileImageSerializer(obj.profile_ptr.image).data
        return None


class BusinessProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Business Profiles."""

    username = serializers.CharField()
    user = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())
    business_name = serializers.CharField()
    business_category = serializers.ChoiceField(
        choices=BusinessProfile.BusinessCategory.choices
    )
    about = serializers.CharField(required=False, allow_blank=True, default="")
    website = serializers.URLField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    business_hours = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "public_id",
            "username",
            "user",
            "business_name",
            "business_category",
            "about",
            "website",
            "phone",
            "business_hours",
        ]
        read_only_fields = ["id", "public_id"]

    def create(self, validated_data):
        """Create BusinessProfile (which also creates the base Profile)."""
        # Extract parent Profile fields
        username = validated_data.pop("username")
        user = validated_data.pop("user")

        # Create BusinessProfile (automatically creates Profile via multi-table inheritance)
        business_profile = BusinessProfile.objects.create(
            username=username, user=user, **validated_data
        )

        return business_profile

    def to_representation(self, instance):
        """Use the read serializer for output."""
        return BusinessProfileSerializer(instance).data


class BusinessProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Business Profiles."""

    username = serializers.CharField(required=False)
    business_name = serializers.CharField(required=False)
    business_category = serializers.ChoiceField(
        choices=BusinessProfile.BusinessCategory.choices, required=False
    )
    about = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    business_hours = serializers.JSONField(required=False)
    is_private = serializers.BooleanField(required=False)

    class Meta:
        model = BusinessProfile
        fields = [
            "username",
            "business_name",
            "business_category",
            "about",
            "website",
            "phone",
            "business_hours",
            "is_private",
        ]

    def update(self, instance, validated_data):
        """Update BusinessProfile and parent Profile fields."""
        # Update parent Profile fields if provided
        if "username" in validated_data:
            instance.profile_ptr.username = validated_data.pop("username")
        if "is_private" in validated_data:
            instance.profile_ptr.is_private = validated_data.pop("is_private")

        # Save parent if any parent fields were updated
        if "username" in self.initial_data or "is_private" in self.initial_data:
            instance.profile_ptr.save()
            # Refresh to prevent child save from overwriting parent with cached values
            instance.refresh_from_db()

        # Update BusinessProfile fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        return instance

    def to_representation(self, instance):
        """Use the read serializer for output."""
        return BusinessProfileSerializer(instance).data


class BusinessProfileDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Business Profiles (includes counts and relationships)."""

    image = serializers.SerializerMethodField()
    address = AddressSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    username = serializers.CharField(source="profile_ptr.username", read_only=True)
    is_private = serializers.BooleanField(
        source="profile_ptr.is_private", read_only=True
    )
    is_following = serializers.SerializerMethodField()
    follows_you = serializers.SerializerMethodField()
    has_requested_follow = serializers.SerializerMethodField()
    can_view_posts = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "public_id",
            "username",
            "business_name",
            "business_category",
            "about",
            "website",
            "phone",
            "address",
            "verified",
            "subscription_tier",
            "analytics_enabled",
            "business_hours",
            "image",
            "is_private",
            "is_following",
            "follows_you",
            "has_requested_follow",
            "can_view_posts",
            "posts_count",
            "followers_count",
            "following_count",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["business"]:
        return "business"

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_image(self, obj):
        """Get image from the parent Profile."""
        if hasattr(obj.profile_ptr, "image"):
            return ProfileImageSerializer(obj.profile_ptr.image).data
        return None

    def get_is_following(self, obj) -> bool:
        """Check if requesting profile is following this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.profile_ptr.following.filter(
                followed_by=current_profile
            ).exists()
        return False

    def get_follows_you(self, obj) -> bool:
        """Check if this profile is following the requesting profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.profile_ptr.followers.filter(followed=current_profile).exists()
        return False

    def get_has_requested_follow(self, obj) -> bool:
        """Check if requesting profile has a pending follow request to this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return FollowRequest.objects.filter(
                requester=current_profile, target=obj.profile_ptr
            ).exists()
        return False

    def get_can_view_posts(self, obj) -> bool:
        """Check if requesting profile can view this profile's posts."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        # Can always view own posts
        if current_profile and obj.profile_ptr == current_profile:
            return True
        # Public profiles are visible to all
        if not obj.profile_ptr.is_private:
            return True
        # Private profiles require following
        if current_profile:
            return obj.profile_ptr.following.filter(
                followed_by=current_profile
            ).exists()
        return False

    def get_posts_count(self, obj) -> int:
        """Get count of posts for this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        posts = obj.profile_ptr.posts.all()

        # if profile is fetching own posts, return all including reported inappropriate
        if current_profile and obj.profile_ptr == current_profile:
            return posts.count()
        # filter posts that have been reported as inappropriate from count
        return posts.filter(~Q(reports__reason__id=1)).count()

    def get_followers_count(self, obj) -> int:
        """Get count of followers."""
        return obj.profile_ptr.following.count()

    def get_following_count(self, obj) -> int:
        """Get count of profiles this profile is following."""
        return obj.profile_ptr.followers.count()


# ============================================================================
# Generic/Polymorphic Profile Serializers
# ============================================================================


class ProfileSerializer(serializers.ModelSerializer):
    """
    Generic Profile serializer for polymorphic use cases.
    This is used when querying Profile.objects.all() and need to serialize mixed types.
    """

    image = ProfileImageSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    breed = serializers.SerializerMethodField()
    pet_type = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "about",
            "image",
            "breed",
            "pet_type",
            "is_private",
            "profile_type",
        ]
        read_only_fields = [
            "id",
            "image",
            "profile_type",
            "name",
            "about",
            "breed",
            "pet_type",
            "is_private",
        ]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

    def get_name(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.name
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.business_name
        return ""

    def get_about(self, obj):
        """Get about from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.about
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.about
        return ""

    def get_breed(self, obj):
        """Get breed from RegularProfile."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.breed
        return ""

    def get_pet_type(self, obj):
        """Get pet_type from RegularProfile."""
        if hasattr(obj, "regularprofile") and obj.regularprofile.pet_type:
            return PetTypeSerializer(obj.regularprofile.pet_type).data
        return None


class ProfileOptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Profile option (used in user profile lists).
    Returns minimal profile info for selection/listing.
    """

    image = ProfileImageSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["id", "public_id", "username", "image", "name", "profile_type"]
        read_only_fields = ["profile_type", "name"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

    def get_name(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.name
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.business_name
        return ""


# ============================================================================
# Legacy/Compatibility Serializers
# ============================================================================


class ProfileCreateSerializer(serializers.ModelSerializer):
    """
    Legacy profile creation serializer.
    Maintained for backward compatibility - creates RegularProfile by default.
    """

    name = serializers.CharField(required=False, allow_blank=True, default="")
    about = serializers.CharField(required=False, allow_blank=True, default="")
    breed = serializers.CharField(required=False, allow_blank=True, default="")
    pet_type = serializers.PrimaryKeyRelatedField(
        queryset=PetType.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "about",
            "user",
            "breed",
            "pet_type",
        ]

    def validate_username(self, value):
        profile = getattr(self.context.get("request"), "current_profile", None)
        profile_id = profile.id if profile else None
        return _validate_username_profanity(value, profile_id=profile_id)

    def create(self, validated_data):
        """Create RegularProfile (maintains backward compatibility)."""
        # Extract child-specific fields
        name = validated_data.pop("name", "")
        about = validated_data.pop("about", "")
        breed = validated_data.pop("breed", "")
        pet_type = validated_data.pop("pet_type", None)

        # Create RegularProfile
        regular_profile = RegularProfile.objects.create(
            name=name, about=about, breed=breed, pet_type=pet_type, **validated_data
        )

        # Return the Profile instance with regularprofile loaded
        return Profile.objects.select_related("regularprofile").get(
            pk=regular_profile.pk
        )

    def to_representation(self, instance):
        """Convert instance to representation."""
        ret = {
            "id": instance.id,
            "public_id": str(instance.public_id) if instance.public_id else None,
            "username": instance.username,
            "user": instance.user_id,
            "name": "",
            "about": "",
            "breed": "",
            "pet_type": None,
        }

        if hasattr(instance, "regularprofile"):
            ret["name"] = instance.regularprofile.name
            ret["about"] = instance.regularprofile.about
            ret["breed"] = instance.regularprofile.breed
            ret["pet_type"] = instance.regularprofile.pet_type_id

        return ret


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Legacy profile update serializer.
    Maintained for backward compatibility - updates based on profile type.
    """

    name = serializers.CharField(required=False, allow_blank=True)
    about = serializers.CharField(required=False, allow_blank=True)
    breed = serializers.CharField(required=False, allow_blank=True)
    is_private = serializers.BooleanField(required=False)
    public_id = serializers.SerializerMethodField()
    pet_type = serializers.PrimaryKeyRelatedField(
        queryset=PetType.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "about",
            "image",
            "breed",
            "pet_type",
            "is_private",
        ]
        read_only_fields = ["id", "image"]

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def _get_profile_id(self):
        profile = getattr(self.context.get("request"), "current_profile", None)
        return profile.id if profile else None

    def validate_username(self, value):
        return _validate_username_profanity(value, profile_id=self._get_profile_id())

    def validate_name(self, value):
        return _validate_profanity(value, "name", "NAME", profile_id=self._get_profile_id())

    def validate_breed(self, value):
        return _validate_profanity(value, "breed", "BREED", profile_id=self._get_profile_id())

    def validate_about(self, value):
        return _validate_text_profanity(value, "about text", "ABOUT", profile_id=self._get_profile_id())

    def update(self, instance, validated_data):
        """Update Profile and its child class fields."""
        # Extract child-specific fields
        name = validated_data.pop("name", None)
        about = validated_data.pop("about", None)
        breed = validated_data.pop("breed", None)
        pet_type = validated_data.pop("pet_type", None)

        # Update the base Profile fields (username, is_private)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        instance.refresh_from_db()

        # Update child class fields
        if hasattr(instance, "regularprofile"):
            regular_profile = instance.regularprofile
            if name is not None:
                regular_profile.name = name
            if about is not None:
                regular_profile.about = about
            if breed is not None:
                regular_profile.breed = breed
            if pet_type is not None:
                regular_profile.pet_type = pet_type
            regular_profile.save()
        elif hasattr(instance, "businessprofile"):
            business_profile = instance.businessprofile
            if about is not None:
                business_profile.about = about
            business_profile.save()

        return instance


class ProfileDetailedSerializer(serializers.ModelSerializer):
    """
    Legacy detailed profile serializer.
    Maintained for backward compatibility - works with mixed profile types.
    """

    image = ProfileImageSerializer(read_only=True)
    is_following = serializers.SerializerMethodField()
    follows_you = serializers.SerializerMethodField()
    has_requested_follow = serializers.SerializerMethodField()
    can_view_posts = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    pet_type = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    breed = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "about",
            "image",
            "is_private",
            "is_following",
            "follows_you",
            "has_requested_follow",
            "can_view_posts",
            "posts_count",
            "followers_count",
            "following_count",
            "breed",
            "pet_type",
            "profile_type",
        ]

    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_name(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.name
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.business_name
        return ""

    def get_about(self, obj):
        """Get about from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.about
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.about
        return ""

    def get_breed(self, obj):
        """Get breed from RegularProfile."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.breed
        return ""

    def get_pet_type(self, obj):
        """Get pet_type from RegularProfile."""
        if hasattr(obj, "regularprofile") and obj.regularprofile.pet_type:
            return PetTypeSerializer(obj.regularprofile.pet_type).data
        return None

    def get_is_following(self, obj) -> bool:
        # boolean - is requesting profile following the profile being fetched
        current_profile = getattr(self.context["request"], "current_profile", None)

        if current_profile:
            return obj.following.filter(followed_by=current_profile).exists()
        return False

    def get_follows_you(self, obj) -> bool:
        """Check if this profile is following the requesting profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return obj.followers.filter(followed=current_profile).exists()
        return False

    def get_has_requested_follow(self, obj) -> bool:
        """Check if requesting profile has a pending follow request to this profile."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        if current_profile:
            return FollowRequest.objects.filter(
                requester=current_profile, target=obj
            ).exists()
        return False

    def get_can_view_posts(self, obj) -> bool:
        """Check if requesting profile can view this profile's posts."""
        current_profile = getattr(self.context["request"], "current_profile", None)
        # Can always view own posts
        if current_profile and obj == current_profile:
            return True
        # Public profiles are visible to all
        if not obj.is_private:
            return True
        # Private profiles require following
        if current_profile:
            return obj.following.filter(followed_by=current_profile).exists()
        return False

    def get_posts_count(self, obj) -> int:
        current_profile = getattr(self.context["request"], "current_profile", None)
        posts = obj.posts.all()

        # if profile is fetching own posts, return all including reported inappropriate
        if current_profile and obj == current_profile:
            return posts.count()
        # filter posts that have been reported as inappropriate from count
        return posts.filter(~Q(reports__reason__id=1)).count()

    def get_followers_count(self, obj) -> int:
        followers = obj.following.all()
        return followers.count()

    def get_following_count(self, obj) -> int:
        following = obj.followers.all()
        return following.count()


# ============================================================================
# Profile Search Serializer
# ============================================================================


class SearchProfileSerializer(serializers.ModelSerializer):
    """Serializer for searching profiles."""

    image = ProfileImageSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    public_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    follows_you = serializers.SerializerMethodField()
    has_requested_follow = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "public_id",
            "username",
            "name",
            "image",
            "is_private",
            "is_following",
            "follows_you",
            "has_requested_follow",
            "profile_type",
            "about",
        ]

    def get_profile_type(self, obj) -> Literal["regular", "business"]:
        """Returns 'regular' or 'business'."""
        return obj.get_profile_type()

    def get_public_id(self, obj):
        return str(obj.public_id) if obj.public_id else None

    def get_name(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.name
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.business_name
        return ""

    def get_about(self, obj):
        """Get name from the specific profile type."""
        if hasattr(obj, "regularprofile"):
            return obj.regularprofile.about
        elif hasattr(obj, "businessprofile"):
            return obj.businessprofile.about
        return ""

    def get_is_following(self, obj) -> bool:
        """Check if requesting profile is following this profile."""
        # Use annotation if available (optimized for list views)
        if hasattr(obj, "_is_following"):
            return obj._is_following
        # Fallback to query (for single object views)
        profile_id = self.context.get("profile_id")
        if profile_id:
            return obj.following.filter(followed_by=profile_id).exists()
        return False

    def get_follows_you(self, obj) -> bool:
        """Check if this profile is following the requesting profile."""
        # Use annotation if available (optimized for list views)
        if hasattr(obj, "_follows_you"):
            return obj._follows_you
        # Fallback to query (for single object views)
        profile_id = self.context.get("profile_id")
        if profile_id:
            return obj.followers.filter(followed=profile_id).exists()
        return False

    def get_has_requested_follow(self, obj) -> bool:
        """Check if requesting profile has a pending follow request to this profile."""
        # Use annotation if available (optimized for list views)
        if hasattr(obj, "_has_requested_follow"):
            return obj._has_requested_follow
        # Fallback to query (for single object views)
        profile_id = self.context.get("profile_id")
        if profile_id:
            return FollowRequest.objects.filter(
                requester_id=profile_id, target=obj
            ).exists()
        return False

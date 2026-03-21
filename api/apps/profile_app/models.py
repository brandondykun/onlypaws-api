"""
Profile app models.
"""
import os
import ulid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_ulid.models import ULIDField

from apps.core_app.utils import crop_to_aspect_ratio_and_resize


class PetType(models.Model):
    """Types of pet."""

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    name = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Address(models.Model):
    """Address model for business profiles."""

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    street_address = models.CharField(max_length=255, blank=True, default="")
    street_address_2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)

    # For international or non-standard addresses
    full_address_text = models.TextField(
        blank=True,
        default="",
        help_text="Full address as text. Use this for international addresses that don't fit the standard fields."
    )

    def __str__(self):
        if self.full_address_text:
            return self.full_address_text
        elif self.street_address:
            return f"{self.street_address}, {self.city}, {self.state}"
        else:
            return "Address (empty)"
    
    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"


class Profile(models.Model):
    """Base profile model for all profile types (multi-table inheritance).
    
    This is a concrete model (not abstract) so we can query all profiles together
    and maintain relationships with other models (Post, Like, Comment, etc.).
    """

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    # Common fields for all profile types
    username = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profiles"
    )
    is_active = models.BooleanField(default=True)
    is_private = models.BooleanField(
        default=False,
        help_text="If true, only approved followers can see posts"
    )
    # Using default instead of auto_now_add for initial migration to populate existing rows
    # Will change to auto_now_add in a later migration after data is populated
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    updated_at = models.DateTimeField(default=timezone.now, blank=True)

    def __str__(self):
        return self.username
    
    def get_profile_type(self):
        """Returns the profile type as a string: 'regular' or 'business'."""
        if hasattr(self, 'regularprofile'):
            return 'regular'
        elif hasattr(self, 'businessprofile'):
            return 'business'
        else:
            # Fallback for profiles that haven't been migrated yet
            return 'regular'
    
    def get_specific_profile(self):
        """Returns the actual RegularProfile or BusinessProfile instance."""
        if hasattr(self, 'regularprofile'):
            return self.regularprofile
        elif hasattr(self, 'businessprofile'):
            return self.businessprofile
        else:
            # Return self if no specific profile exists yet (during migration)
            return self
    
    def is_regular_profile(self):
        """Returns True if this is a regular (pet) profile."""
        return hasattr(self, 'regularprofile')
    
    def is_business_profile(self):
        """Returns True if this is a business profile."""
        return hasattr(self, 'businessprofile')


class RegularProfile(Profile):
    """Regular profile for pets (personal accounts).
    
    Inherits from Profile using multi-table inheritance.
    This creates a separate table with a OneToOne link to Profile.
    """
    
    # Profile description
    about = models.CharField(
        max_length=1000,
        blank=True,
        default="",
        help_text="About this pet profile"
    )
    
    # Pet-specific fields
    name = models.CharField(
        max_length=64, 
        default="", 
        blank=True,
        help_text="Name of the pet"
    )
    pet_type = models.ForeignKey(
        PetType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="regular_profiles",
        blank=True,
        help_text="Type of pet (dog, cat, etc.)"
    )
    breed = models.CharField(
        max_length=64,
        default="",
        blank=True,
        help_text="Breed of the pet"
    )
    
    class Meta:
        verbose_name = "Regular Profile"
        verbose_name_plural = "Regular Profiles"
    
    def __str__(self):
        return f"{self.username} (Regular)"


class BusinessProfile(Profile):
    """Business profile for pet-related businesses.
    
    Inherits from Profile using multi-table inheritance.
    This creates a separate table with a OneToOne link to Profile.
    """
    
    class BusinessCategory(models.TextChoices):
        VETERINARY = "VETERINARY", _("Veterinary Clinic")
        SHELTER = "SHELTER", _("Animal Shelter")
        RESCUE = "RESCUE", _("Animal Rescue")
        GROOMING = "GROOMING", _("Pet Grooming")
        TRAINING = "TRAINING", _("Pet Training")
        PET_STORE = "PET_STORE", _("Pet Store")
        BREEDER = "BREEDER", _("Breeder")
        BOARDING = "BOARDING", _("Pet Boarding")
        DAYCARE = "DAYCARE", _("Pet Daycare")
        PET_SITTING = "PET_SITTING", _("Pet Sitting")
        PHOTOGRAPHY = "PHOTOGRAPHY", _("Pet Photography")
        WALKER = "WALKER", _("Pet Walker")
        OTHER = "OTHER", _("Other Pet Business")
    
    class SubscriptionTier(models.TextChoices):
        FREE = "FREE", _("Free")
        BASIC = "BASIC", _("Basic")
        PREMIUM = "PREMIUM", _("Premium")
        ENTERPRISE = "ENTERPRISE", _("Enterprise")
    
    # Profile description (longer for businesses)
    about = models.CharField(
        max_length=2000, blank=True, default="", help_text="About this business profile"
    )
    # Business-specific fields
    business_name = models.CharField(
        max_length=100, help_text="Official business name"
    )
    business_category = models.CharField(
        max_length=20, choices=BusinessCategory.choices, default=BusinessCategory.OTHER, help_text="Type of pet business"
    )
    website = models.URLField(
        max_length=200, blank=True, default="", help_text="Business website URL"
    )
    phone = models.CharField(
        max_length=20, blank=True, default="", help_text="Business phone number"
    )
    address = models.OneToOneField(
        Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="business_profile", help_text="Business address"
    )
    verified = models.BooleanField(
        default=False, help_text="Whether the business has been verified by admin"
    )
    subscription_tier = models.CharField(
        max_length=20, choices=SubscriptionTier.choices, default=SubscriptionTier.FREE, help_text="Business subscription tier"
    )
    analytics_enabled = models.BooleanField(
        default=False, help_text="Whether analytics tracking is enabled for this business"
    )
    business_hours = models.JSONField(
        default=dict, blank=True, help_text="Business operating hours in JSON format"
    )
    
    class Meta:
        verbose_name = "Business Profile"
        verbose_name_plural = "Business Profiles"
    
    def __str__(self):
        return f"{self.username} - {self.business_name} (Business)"


def _profile_env_prefix():
    """Return the environment prefix for profile storage keys."""
    env = os.environ.get("DJANGO_ENV")
    if env == "test":
        return "images/test/"
    if env == "dev":
        return "images/dev/"
    if env == "e2e":
        return "images/e2e/"
    return "images/"


def profile_image_path(instance, filename):
    """Generate S3 path (key) for saving profile image.
    Key: {env_prefix}profiles/<profile.public_id>/avatar_400.webp
    """
    prefix = _profile_env_prefix()
    public_id = str(instance.profile.public_id)
    return f"{prefix}profiles/{public_id}/avatar_400.webp"


def profile_scaled_path(instance, filename):
    """Generate S3 path for scaled profile images.
    Key: {env_prefix}profiles/<profile.public_id>/avatar_<scale_dimension>.webp
    """
    prefix = _profile_env_prefix()
    public_id = str(instance.profile_image.profile.public_id)
    dim = ProfileImageScaled.SCALE_DIMENSIONS[instance.scale]
    return f"{prefix}profiles/{public_id}/avatar_{dim}.webp"


class ProfileImage(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING_UPLOAD = "PENDING_UPLOAD", "Pending Upload"
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    profile = models.OneToOneField(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="image"
    )
    image = models.ImageField(upload_to=profile_image_path, blank=True, null=True)
    original_key = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="S3 key for the original uploaded image (before processing)",
    )
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.READY,
        help_text="Image processing status",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Legacy direct upload: no original_key, process image in save (crop/resize)
        update_fields = kwargs.get("update_fields", None)
        should_process_image = (
            self.original_key is None
            and self.image
            and (
                self.pk is None
                or update_fields is None
                or (update_fields is not None and "image" in update_fields)
            )
        )
        if should_process_image:
            # Match presigned-URL flow (ProfileImageScaled.SCALE_DIMENSIONS["large"])
            self.image = crop_to_aspect_ratio_and_resize(
                self.image,
                aspect_ratio="1:1",
                base_width=ProfileImageScaled.SCALE_DIMENSIONS["large"],
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profile {self.profile.id} - {self.image.name if self.image else 'no image'}"


class ProfileImageScaled(models.Model):
    """
    Stores scaled variants of ProfileImage for different display contexts.
    LARGE (400px) is stored in ProfileImage.image; this model stores medium and small.
    Sizes chosen for avatars: large for profile/zoom, medium for cards, small for lists.
    """

    class Scale(models.TextChoices):
        SMALL = "small", "Small"  # 100px – lists, comments
        MEDIUM = "medium", "Medium"  # 200px – cards, feeds

    SCALE_DIMENSIONS = {
        "small": 100,
        "medium": 200,
        "large": 400,  # Used for ProfileImage.image; matches common social (320–400)
    }

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    profile_image = models.ForeignKey(
        "ProfileImage",
        on_delete=models.CASCADE,
        related_name="scaled_images",
    )
    scale = models.CharField(max_length=20, choices=Scale.choices)
    image = models.ImageField(upload_to=profile_scaled_path)
    width = models.PositiveIntegerField(help_text="Width in pixels")
    height = models.PositiveIntegerField(help_text="Height in pixels")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["profile_image", "scale"]]
        indexes = [
            models.Index(fields=["profile_image", "scale"]),
        ]

    def __str__(self):
        return f"ProfileImage {self.profile_image.id} - {self.scale}"


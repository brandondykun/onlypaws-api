"""
Profile app models.
"""
import os
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.core_app.utils import crop_square_and_resize


class PetType(models.Model):
    """Types of pet."""

    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name


class Address(models.Model):
    """Address model for business profiles."""
    
    street_address = models.CharField(max_length=255, blank=True, default="")
    street_address_2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    
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

    # Common fields for all profile types
    username = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profiles"
    )
    is_active = models.BooleanField(default=True)
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


def profile_image_path(instance, filename):
    """Generate S3 path (key) for saving profile image.
    The key is {user_id}/{profile_id}/profile_image.webp
    On update, the same key is generated which automatically overwrites the image in S3.
    """
    user_id = instance.profile.user.id
    profile_id = instance.profile.id
    path = "images/{0}/{1}/{2}".format(user_id, profile_id, filename)
    # build path based on environment
    if os.environ.get("DJANGO_ENV") == "test":
        path = "images/test/{0}/{1}/{2}".format(user_id, profile_id, filename)
    if os.environ.get("DJANGO_ENV") == "dev":
        path = "images/dev/{0}/{1}/{2}".format(user_id, profile_id, filename)
    return path


class ProfileImage(models.Model):
    profile = models.OneToOneField(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="image"
    )
    image = models.ImageField(upload_to=profile_image_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.image = crop_square_and_resize(self.image, image_size=320)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profile {self.profile.id} - {self.image.name}"


import os
import logging
import traceback
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxLengthValidator

from django.db import models
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from .utils import crop_square_and_resize
from datetime import timedelta
from django.utils import timezone

from pgvector.django import VectorField, CosineDistance

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    """Manager for users."""

    def create_user(self, email, password=None, **extra_fields):
        """Create, save and return new user."""
        if not email:
            raise ValueError("User must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        """Create and return new superuser."""
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system."""

    email = models.EmailField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email


class VerifyEmailToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verify_email_token",
    )
    token = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.token}"


class ResetPasswordToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reset_password_token",
    )
    token = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.token}"


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
    
    # TEMPORARY: Legacy fields for migration - will be removed after data migration
    # These are being moved to specific profile types but kept here temporarily
    about = models.CharField(
        max_length=1000, blank=True, default="",
        help_text="DEPRECATED: Will be moved to RegularProfile/BusinessProfile"
    )
    name = models.CharField(
        max_length=64, default="", blank=True,
        help_text="DEPRECATED: Will be moved to RegularProfile"
    )
    pet_type = models.ForeignKey(
        PetType, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="legacy_profiles",  # Changed to avoid conflict with RegularProfile
        blank=True,
        help_text="DEPRECATED: Will be moved to RegularProfile"
    )
    breed = models.CharField(
        max_length=64, default="", blank=True,
        help_text="DEPRECATED: Will be moved to RegularProfile"
    )

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
    about_new = models.CharField(
        max_length=1000,
        blank=True,
        default="",
        help_text="About this pet profile"
    )
    
    # Pet-specific fields
    name_new = models.CharField(
        max_length=64, 
        default="", 
        blank=True,
        help_text="Name of the pet"
    )
    pet_type_new = models.ForeignKey(
        PetType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="regular_profiles",
        blank=True,
        help_text="Type of pet (dog, cat, etc.)"
    )
    breed_new = models.CharField(
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
    about_new = models.CharField(
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
        Profile, on_delete=models.CASCADE, related_name="image"
    )
    image = models.ImageField(upload_to=profile_image_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.image = crop_square_and_resize(self.image, image_size=320)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profile {self.profile.id} - {self.image.name}"


class Post(models.Model):
    """Post with image and text."""

    caption = models.TextField(validators=[MaxLengthValidator(1000, message="Caption cannot exceed 1000 characters.")])
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contains_ai = models.BooleanField(blank=True, default=False)

    def __str__(self):
        return f"Post {self.id} - {self.caption}"


def post_image_path(instance, filename):
    """Generate S3 path (key) for saving post image.
    The key is {user_id}/{profile_id}/{post_id}/{filename}.webp
    """
    user_id = instance.post.profile.user.id
    profile_id = instance.post.profile.id
    post_id = instance.post.id
    path = "{0}/{1}/{2}/{3}".format(user_id, profile_id, post_id, filename)
    # build path based on environment
    if os.environ.get("DJANGO_ENV") == "test":
        path = "images/test/" + path
    elif os.environ.get("DJANGO_ENV") == "dev":
        path = "images/dev/" + path
    else:
        path = "images/" + path

    return path


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=post_image_path)
    order = models.IntegerField(default=0, help_text="Display order of the image in the post")

    # Embedding fields for similarity search
    embedding = VectorField(
        dimensions=512,  # 512-dimensional embedding
        null=True,
        blank=True,
        help_text="Vector embedding for similarity search",
    )
    embedding_model = models.CharField(
        max_length=100,
        default="clip-vit-base-patch32",
        help_text="Model used to generate the embedding",
    )
    embedding_generated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the embedding was generated"
    )

    def save(self, *args, **kwargs):
        # Process image
        self.image = crop_square_and_resize(self.image, image_size=1080)

        # Check if we need to generate embedding
        should_generate_embedding = (
            self.pk is None  # New instance
            or "embedding"
            not in kwargs.get("update_fields", [])  # Not updating embedding field
        )

        # Save first to ensure we have a file path
        super().save(*args, **kwargs)

        # Generate embedding asynchronously if needed
        if should_generate_embedding and (
            self.embedding is None
            or (hasattr(self.embedding, "__len__") and len(self.embedding) == 0)
        ):
            try:
                # Import here to avoid circular imports
                from .tasks import generate_image_embedding_task
                from django.db import transaction

                def queue_embedding_task():
                    """Queue the embedding task after transaction commits."""
                    try:
                        task = generate_image_embedding_task.delay(self.id)
                        logger.info(
                            f"Queued embedding generation task {task.id} for PostImage {self.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to queue embedding task for PostImage {self.id}: {str(e)}"
                        )

                # Queue the task only after the transaction commits
                # This ensures the PostImage exists in the database when the worker runs
                transaction.on_commit(queue_embedding_task)

            except Exception as e:
                # Fallback to synchronous generation if Celery is not available
                logger.warning(
                    f"Failed to queue async embedding task for PostImage {self.id}, "
                    f"falling back to synchronous generation: {str(e)}"
                )

                try:
                    from .services import get_embedding_service

                    get_embedding_service().generate_embedding_for_post_image(self)
                except Exception as sync_error:
                    logger.error(
                        f"Synchronous embedding generation also failed for PostImage {self.id}: {str(sync_error)}"
                    )

    def find_similar_images(self, limit: int = 10, min_similarity: float = 0.1):
        """
        Find similar images based on embedding similarity using pgvector.

        Args:
            limit: Maximum number of similar images to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            QuerySet of similar PostImage instances ordered by similarity
        """
        if self.embedding is None or (
            hasattr(self.embedding, "__len__") and len(self.embedding) == 0
        ):
            return PostImage.objects.none()

        # Use pgvector's CosineDistance for similarity search
        # CosineDistance returns values from 0 (identical) to 2 (opposite)
        # So max_distance = 2 * (1 - min_similarity)
        max_distance = 2 * (1 - min_similarity)

        try:
            return (
                PostImage.objects.filter(embedding__isnull=False)
                .exclude(id=self.id)  # Exclude self
                .annotate(distance=CosineDistance("embedding", self.embedding))
                .filter(distance__lte=max_distance)
                .order_by("distance")[:limit]
            )
        except Exception as e:
            logger.error(f"Error in pgvector query: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Fallback to empty queryset
            return PostImage.objects.none()

    def __str__(self):
        return f"Post {self.post.id} - {self.image.name}"

    class Meta:
        ordering = ["order", "id"]


class Like(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.post}"

    class Meta:
        unique_together = (("profile", "post"),)


class Comment(models.Model):
    text = models.CharField(max_length=1000)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="comments"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="all_replies",
        null=True,
        blank=True,
    )
    reply_to_comment = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True
    )

    def __str__(self):
        return self.text


class Follow(models.Model):
    followed = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="following"
    )
    followed_by = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="followers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.followed_by.username} follows {self.followed.username}"

    class Meta:
        unique_together = (("followed", "followed_by"),)


class CommentLike(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="comment_likes"
    )
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.comment}"

    class Meta:
        unique_together = (("profile", "comment"),)


def post_image_staging_path(instance, filename):
    """Generate S3 path (key) for saving staged post image.
    This is a temporary key, that will be overwritten once the post is created.
    """
    user_id = instance.profile.user.id
    profile_id = instance.profile.id
    post_uuid = instance.post_uuid
    return "images/{0}/{1}/staged/{2}/{3}".format(
        user_id, profile_id, post_uuid, filename
    )


class PostImageStaged(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="staged_images"
    )
    post_uuid = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=post_image_staging_path)

    def save(self, *args, **kwargs):
        self.image = crop_square_and_resize(self.image, image_size=1080)
        super().save(*args, **kwargs)


class SavedPost(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="saved_posts"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("profile", "post"),)


class ReportReason(models.Model):
    """
    Model to store predefined reasons for reporting posts
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class PostReport(models.Model):
    """
    Model to store reports made by users on posts
    """

    class ReportStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending Review")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under Review")
        RESOLVED = "RESOLVED", _("Resolved")
        DISMISSED = "DISMISSED", _("Dismissed")

    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        "Profile", on_delete=models.SET_NULL, null=True, related_name="reported_posts"
    )
    reason = models.ForeignKey(ReportReason, on_delete=models.PROTECT)
    details = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="resolved_reports",
        blank=True,
    )
    resolution_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        # Prevent multiple reports from the same user on the same post
        unique_together = (("post", "reporter"),)

    def __str__(self):
        return f"Report on {self.post} by {self.reporter}"


class PendingEmailChange(models.Model):
    """Stores pending email change requests."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    new_email = models.EmailField()
    verification_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} -> {self.new_email}"

    @property
    def is_expired(self):
        return timezone.now() > (self.created_at + timedelta(hours=12))

    class Meta:
        # Only one pending change per user
        unique_together = [["user", "new_email"]]

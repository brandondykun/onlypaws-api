import os
from django.db import models
from django.utils.translation import gettext_lazy as _

from django.db import models
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from .utils import crop_square_and_resize


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


class Profile(models.Model):
    """Profile for each user."""

    username = models.CharField(max_length=32, unique=True)
    about = models.CharField(max_length=1000, blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profiles"
    )
    name = models.CharField(max_length=64, default="", blank=True)
    pet_type = models.ForeignKey(
        PetType, on_delete=models.SET_NULL, null=True, related_name="type", blank=True
    )
    breed = models.CharField(max_length=64, default="", blank=True)

    def __str__(self):
        return self.username


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


class Post(models.Model):
    """Post with image and text."""

    caption = models.CharField(max_length=128)
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
    is_main = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.image = crop_square_and_resize(self.image, image_size=1080)
        super().save(*args, **kwargs)


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

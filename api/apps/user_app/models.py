"""
User app models.
"""
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


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
    regular_profile_onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed onboarding for RegularProfile type"
    )
    business_profile_onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed onboarding for BusinessProfile type"
    )

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


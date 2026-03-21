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
        """Create, save and return new user. Also creates email AuthProvider."""
        if not email:
            raise ValueError("User must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        AuthProvider.objects.get_or_create(
            user=user,
            provider=AuthProvider.Provider.EMAIL,
            defaults={"external_id": user.email, "metadata": {}},
        )
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

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email

    def has_auth_provider(self, provider):
        """Return True if the user has an auth provider for the given provider."""
        return self.auth_providers.filter(provider=provider).exists()


class AuthProvider(models.Model):
    """
    Represents a single auth provider linked to a user.
    A user can have multiple auth providers (e.g. email + Google).
    Used for email/password (default), and future providers (Google, Apple, etc.).
    """

    class Provider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_providers",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices, db_index=True)
    external_id = models.CharField(
        max_length=255,
        help_text="Provider-specific identifier (e.g. email for email provider, OAuth sub for Google/Apple).",
    )
    token_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific token data (e.g. OAuth refresh token). Not used for email.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata returned by the provider.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                name="auth_provider_provider_external_id_uniq",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="auth_provider_user_provider_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "external_id"]),
        ]

    def __str__(self):
        return f"{self.user_id} ({self.provider}: {self.external_id})"


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

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    new_email = models.EmailField()
    verification_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} -> {self.new_email}"

    @property
    def is_expired(self):
        return timezone.now() > (self.created_at + timedelta(hours=12))


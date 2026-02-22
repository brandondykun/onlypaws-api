"""
Authentication services for multi-provider auth.

- Email/password: handled by Django auth and UserManager (creates AuthProvider).
- Future providers (Google, Apple): use get_user_by_provider or get_or_create_user_for_provider.
"""
import logging

from django.contrib.auth import get_user_model

from .models import AuthProvider

logger = logging.getLogger(__name__)


def get_user_by_provider(provider: str, external_id: str):
    """
    Return the User linked to the given provider and external_id, or None.

    Use for login flows where the user must already exist (e.g. link account).
    """
    try:
        auth_provider = AuthProvider.objects.select_related("user").get(
            provider=provider, external_id=external_id
        )
        return auth_provider.user
    except AuthProvider.DoesNotExist:
        return None


def get_or_create_user_for_provider(
    provider: str,
    external_id: str,
    email: str | None = None,
    token_data: dict | None = None,
    metadata: dict | None = None,
):
    """
    Get existing user by provider+external_id, or create a new User and AuthProvider.

    For OAuth providers (Google, Apple): pass email from provider for new users.
    token_data and metadata are stored on AuthProvider.

    Returns (user, created).
    """
    User = get_user_model()
    auth_provider = (
        AuthProvider.objects.select_related("user")
        .filter(provider=provider, external_id=external_id)
        .first()
    )
    if auth_provider:
        # Update token_data/metadata if provided
        if token_data is not None or metadata is not None:
            if token_data is not None:
                auth_provider.token_data = token_data
            if metadata is not None:
                auth_provider.metadata = metadata or {}
            auth_provider.save(update_fields=["token_data", "metadata", "updated_at"])
        return auth_provider.user, False

    if not email and provider != AuthProvider.Provider.EMAIL:
        raise ValueError("email is required when creating a new user for a non-email provider")

    # Create new user and auth provider
    if provider == AuthProvider.Provider.EMAIL:
        # Email provider normally uses UserManager.create_user with password.
        # This path is for edge cases (e.g. admin creating email auth provider only).
        user = User.objects.filter(email=external_id).first()
        if user:
            AuthProvider.objects.get_or_create(
                user=user,
                provider=AuthProvider.Provider.EMAIL,
                defaults={"external_id": external_id, "metadata": metadata or {}},
            )
            return user, False
        raise ValueError("For email provider use User.objects.create_user()")

    # OAuth: link to existing user by email if present, else create new user
    normalized_email = User.objects.normalize_email(email) if email else None
    if normalized_email:
        existing = User.objects.filter(email=normalized_email).first()
        if existing:
            # Account linking: same email already registered (e.g. email sign-up first)
            logger.info(
                "Linking OAuth provider %s (external_id=%s) to existing user %s (id=%s)",
                provider, external_id, normalized_email, existing.id,
            )
            auth_provider, _ = AuthProvider.objects.get_or_create(
                user=existing,
                provider=provider,
                defaults={
                    "external_id": external_id,
                    "token_data": token_data or {},
                    "metadata": metadata or {},
                },
            )
            if token_data is not None or metadata is not None:
                if token_data is not None:
                    auth_provider.token_data = token_data
                if metadata is not None:
                    auth_provider.metadata = metadata or {}
                auth_provider.save(update_fields=["token_data", "metadata", "updated_at"])
            return existing, False

    # New OAuth user: create without going through create_user (no email AuthProvider)
    if not email:
        raise ValueError(
            f"email is required when creating a new user for provider {provider}"
        )
    user = User(
        email=User.objects.normalize_email(email),
    )
    user.set_unusable_password()
    if metadata and metadata.get("email_verified"):
        user.is_email_verified = True
    user.save()
    AuthProvider.objects.create(
        user=user,
        provider=provider,
        external_id=external_id,
        token_data=token_data or {},
        metadata=metadata or {},
    )
    return user, True

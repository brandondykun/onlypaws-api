import os
import json
from pathlib import Path

from rest_framework.exceptions import AuthenticationFailed
from django.utils.functional import SimpleLazyObject
from django.http import JsonResponse
from apps.profile_app.models import Profile
from django.conf import settings


# File-based maintenance flag location
MAINTENANCE_FLAG_FILE = Path("/tmp/maintenance_mode.json")


def get_maintenance_status():
    """
    Check if maintenance mode is enabled.

    Checks both file-based flag (for dev) and environment variable (for prod).
    Returns tuple of (is_enabled, message, end_time, allow_admin)
    """
    # First check file-based flag (takes precedence for easy toggling)
    if MAINTENANCE_FLAG_FILE.exists():
        try:
            data = json.loads(MAINTENANCE_FLAG_FILE.read_text())
            return (
                True,
                data.get("message", "The system is currently undergoing maintenance."),
                data.get("end_time"),
                data.get("allow_admin", False),
            )
        except (json.JSONDecodeError, IOError):
            pass

    # Fall back to environment variable (for production/docker-compose)
    if os.environ.get("MAINTENANCE_MODE", "0") == "1":
        return (
            True,
            os.environ.get(
                "MAINTENANCE_MESSAGE", "The system is currently undergoing maintenance."
            ),
            os.environ.get("MAINTENANCE_END_TIME"),
            os.environ.get("MAINTENANCE_ALLOW_ADMIN", "0") == "1",
        )

    return (False, None, None, False)


class MaintenanceModeMiddleware:
    """
    Middleware to handle maintenance mode.

    Maintenance mode can be enabled via:
    1. File flag at /tmp/maintenance_mode.json (for development)
    2. MAINTENANCE_MODE environment variable (for production)

    When enabled, all requests except those to excluded paths will receive
    a 503 Service Unavailable response.
    """

    # Paths that should always be accessible, even during maintenance
    EXCLUDED_PATHS = [
        "/api/v1/config/status/",  # Status endpoint must always respond
        "/admin/",  # Allow admin access during maintenance (optional)
        "/static/",  # Static files should still be served
        "/.well-known/",  # For SSL certificate renewal
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if maintenance mode is enabled
        is_maintenance, message, end_time, allow_admin = get_maintenance_status()

        if is_maintenance and not self._is_excluded_path(request.path):
            # Check if admin users should be allowed through
            if (
                allow_admin
                and hasattr(request, "user")
                and request.user.is_authenticated
            ):
                if request.user.is_staff or request.user.is_superuser:
                    return self.get_response(request)

            # Return 503 Service Unavailable
            response_data = {
                "status": "maintenance",
                "message": message,
                "estimated_end_time": end_time,
            }

            response = JsonResponse(response_data, status=503)
            response["Content-Type"] = "application/json"
            response["Retry-After"] = "300"  # Suggest retry after 5 minutes

            return response

        return self.get_response(request)

    def _is_excluded_path(self, path):
        """Check if the path should be excluded from maintenance mode checks."""
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)


class ProfileAuthenticationMiddleware:
    """
    Resolve the profile from the auth-profile-id header (profile's public_id, ULID)
    and attach it as request.current_profile.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip middleware for admin and non-API paths
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Attach the profile lazily to prevent unnecessary database queries
        request.current_profile = SimpleLazyObject(lambda: self._get_profile(request))

        return self.get_response(request)

    def _get_profile(self, request):
        # Skip profile validation for excluded paths
        if self._is_excluded_path(request.path, request.method):
            return None

        # Check if user is authenticated
        if not request.user.is_authenticated:
            return None

        # Get profile ID from header
        profile_public_id = request.headers.get("auth-profile-id")

        if not profile_public_id:
            raise AuthenticationFailed(
                detail="Profile public ID not provided in headers",
                code="profile_public_id_missing",
            )

        try:
            profile = request.user.profiles.get(public_id=profile_public_id)
            return profile

        except Profile.DoesNotExist:
            raise AuthenticationFailed(
                detail="Invalid profile public ID", code="profile_public_id_invalid"
            )

    def _is_excluded_path(self, path, method):
        """
        Check if the current path should be excluded from profile validation.
        Add any paths that don't require profile authentication.
        """
        EXCLUDED_PATHS = [
            "/docs",
            "/schema",
            "/api-auth",
            "/admin",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/my-info",
            "/api/v1/config/status",  # Status endpoint is public
        ]

        # Profile creation during onboarding — no profile exists yet
        EXCLUDED_METHOD_PATHS = [
            ("POST", "/api/v1/profile/"),
        ]

        if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
            return True

        if any(
            method == m and path.rstrip("/") == p.rstrip("/")
            for m, p in EXCLUDED_METHOD_PATHS
        ):
            return True

        return False


from django.middleware.csrf import CsrfViewMiddleware


class CustomCsrfMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if any(
            request.path.startswith(path)
            for path in getattr(settings, "CSRF_EXEMPT_PATHS", [])
        ):
            return None
        return super().process_view(request, callback, callback_args, callback_kwargs)

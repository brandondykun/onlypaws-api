from rest_framework.exceptions import AuthenticationFailed
from django.utils.functional import SimpleLazyObject
from .models import Profile


class ProfileAuthenticationMiddleware:
    """
    Middleware to authenticate the profile from the auth-profile-id header
    and attach it to the request object.
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
        if self._is_excluded_path(request.path):
            return None

        # Check if user is authenticated
        if not request.user.is_authenticated:
            return None

        # Get profile ID from header
        profile_id = request.headers.get("auth-profile-id")

        if not profile_id:
            raise AuthenticationFailed(
                detail="Profile ID not provided in headers", code="profile_id_missing"
            )

        try:
            profile = request.user.profiles.get(id=profile_id)
            return profile

        except Profile.DoesNotExist:
            raise AuthenticationFailed(
                detail="Invalid profile ID", code="profile_invalid"
            )

    def _is_excluded_path(self, path):
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
            # Add other paths that don't need profile validation
        ]

        return any(path.startswith(excluded) for excluded in EXCLUDED_PATHS)

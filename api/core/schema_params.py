"""
Shared OpenAPI schema parameters for use across all apps.
"""

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes


# Reusable parameter for API documentation
auth_profile_param = OpenApiParameter(
    name="auth-profile-id",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    description="Public ID (ULID) of the profile making the request (must be authenticated)",
    required=True,
)

# schema query param to search for username by text
username_param = OpenApiParameter(
    "username",
    OpenApiTypes.STR,
    description="Username string or substring to search.",
)

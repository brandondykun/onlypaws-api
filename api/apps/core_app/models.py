"""
DEPRECATED: This file provides backwards-compatible imports only.

All models have been moved to their appropriate apps:
- User models: apps.user_app.models
- Post models: apps.posts_app.models  
- Interaction models: apps.interactions_app.models
- Moderation models: apps.moderation_app.models

Import from the specific apps instead of core_app.models.
This file will be removed in a future version.
"""

# User app models
from apps.user_app.models import (
    User,
    UserManager,
    VerifyEmailToken,
    ResetPasswordToken,
    PendingEmailChange,
    Profile,
    RegularProfile,
    BusinessProfile,
    PetType,
    Address,
    ProfileImage,
)

# Posts app models
from apps.posts_app.models import (
    Post,
    PostImage,
    SavedPost,
)

# Interactions app models
from apps.interactions_app.models import (
    Like,
    Comment,
    CommentLike,
    Follow,
)

# Moderation app models
from apps.moderation_app.models import (
    ReportReason,
    PostReport,
)

__all__ = [
    # User models
    "User",
    "UserManager",
    "VerifyEmailToken",
    "ResetPasswordToken",
    "PendingEmailChange",
    "Profile",
    "RegularProfile",
    "BusinessProfile",
    "PetType",
    "Address",
    "ProfileImage",
    # Post models
    "Post",
    "PostImage",
    "SavedPost",
    # Interaction models
    "Like",
    "Comment",
    "CommentLike",
    "Follow",
    # Moderation models
    "ReportReason",
    "PostReport",
]

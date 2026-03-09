"""
Utility functions for profile blocking.
"""

from django.db.models import Q
from apps.moderation_app.models import Block


def get_blocked_profile_ids(profile):
    """Returns set of profile IDs where a block relationship exists (either direction).

    Uses a single query with UNION via Q objects instead of two separate queries.
    Result is cached on the profile instance to avoid duplicate queries in the same request.
    """
    if hasattr(profile, "_blocked_profile_ids_cache"):
        return profile._blocked_profile_ids_cache

    # Single query: fetch all Block rows where this profile is either side
    blocks = Block.objects.filter(
        Q(blocker=profile) | Q(blocked=profile)
    ).values_list("blocker_id", "blocked_id")

    result = set()
    for blocker_id, blocked_id in blocks:
        # Add the *other* profile's ID (not our own)
        if blocker_id == profile.id:
            result.add(blocked_id)
        else:
            result.add(blocker_id)

    profile._blocked_profile_ids_cache = result
    return result


def are_profiles_blocking(profile_a, profile_b):
    """Check if a block exists between two specific profiles."""
    return Block.objects.filter(
        Q(blocker=profile_a, blocked=profile_b)
        | Q(blocker=profile_b, blocked=profile_a)
    ).exists()

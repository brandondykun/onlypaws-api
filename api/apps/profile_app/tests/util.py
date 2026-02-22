"""
Test utilities for profile app.
"""

from django.urls import reverse


def get_profile_detail_url(profile):
    """Return profile detail URL. profile may be a Profile instance or public_id (str)."""
    public_id = str(profile.public_id) if hasattr(profile, "public_id") else profile
    return reverse("profile_app:retrieve_update_destroy_profile", args=[public_id])


def create_profile_url():
    """Return URL for creating a profile."""
    return reverse("profile_app:create_profile")


def retrieve_update_profile_url(profile):
    """Create and return a retrieve/update profile url. profile may be a Profile instance or public_id (str)."""
    public_id = str(profile.public_id) if hasattr(profile, "public_id") else profile
    return reverse("profile_app:retrieve_update_destroy_profile", args=[public_id])


def search_profiles_url(search_text: str):
    """Create and return a search profiles url.

    Parameters
    ----------
    search_text : str
        Search text of username (partial or full) to be searched.
    """
    return f"{reverse('profile_app:search_profiles')}?username={search_text}"

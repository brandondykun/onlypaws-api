"""
Test utilities for profile app.
"""

from django.urls import reverse


def get_profile_detail_url(profile_id):
    """Return profile detail URL."""
    return reverse("profile_app:retrieve_update_destroy_profile", args=[profile_id])


def create_profile_url():
    """Return URL for creating a profile."""
    return reverse("profile_app:create_profile")


def retrieve_update_profile_url(profile_id):
    """Create and return a retrieve/update profile url."""
    return reverse("profile_app:retrieve_update_destroy_profile", args=[profile_id])


def search_profiles_url(search_text: str):
    """Create and return a search profiles url.

    Parameters
    ----------
    search_text : str
        Search text of username (partial or full) to be searched.
    """
    return f"{reverse('profile_app:search_profiles')}?username={search_text}"

"""
Tests for the search profiles api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, Post


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


# profile id is profile performing search
def search_profiles_url(profile_id, search_text):
    """Create and return a search profiles url."""
    return f"{reverse("posts_app:search_profiles", args=[profile_id])}?username={search_text}"


class PrivateSearchPRofilesApiTests(TestCase):
    """Test the private features of the search profiles API."""

    def setUp(self):
        # create user and profile
        user_details = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        self.user = create_user(**user_details)
        profile_details = {
            "username": "test_username_1",
            "about": "Test about text.",
            "user": self.user,
        }
        self.profile = create_profile(**profile_details)
        # create second user and profile
        user_2_details = {
            "email": "test2@example.com",
            "password": "test-user-password-123",
        }
        self.user_2 = create_user(**user_2_details)
        profile_2_details = {
            "username": "test_username_2",
            "about": "Test about text.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_2_details)
        # create third user and profile
        user_3_details = {
            "email": "test3@example.com",
            "password": "test-user-password-123",
        }
        self.user_3 = create_user(**user_3_details)
        profile_3_details = {
            "username": "test_username_3",
            "about": "Test about text.",
            "user": self.user_3,
        }
        self.profile_3 = create_profile(**profile_3_details)

        # create fourth user and profile
        # this profile username should not contain "user"
        user_4_details = {
            "email": "test4@example.com",
            "password": "test-user-password-123",
        }
        self.user_4 = create_user(**user_4_details)
        profile_4_details = {
            "username": "something_different",  # should not container "user"
            "about": "Test about text.",
            "user": self.user_4,
        }
        self.profile_4 = create_profile(**profile_4_details)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_search_profiles_successful(self):
        """
        Test searching for profiles by username returns results
        that match the searched username text.
        """
        url = search_profiles_url(self.profile.id, "user")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

    def test_search_profiles_without_username_returns_error(self):
        """
        Test searching for profiles by username but not
        providing a username returns error.
        """
        url = search_profiles_url(self.profile.id, "")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PublicSearchPRofilesApiTests(TestCase):
    """Test the public features of the search profiles API."""

    def setUp(self):
        # create user and profile
        user_details = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        self.user = create_user(**user_details)
        profile_details = {
            "username": "test_username_1",
            "about": "Test about text.",
            "user": self.user,
        }
        self.profile = create_profile(**profile_details)
        # create second user and profile
        user_2_details = {
            "email": "test2@example.com",
            "password": "test-user-password-123",
        }
        self.user_2 = create_user(**user_2_details)
        profile_2_details = {
            "username": "test_username_2",
            "about": "Test about text.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_2_details)
        # create third user and profile
        user_3_details = {
            "email": "test3@example.com",
            "password": "test-user-password-123",
        }
        self.user_3 = create_user(**user_3_details)
        profile_3_details = {
            "username": "test_username_3",
            "about": "Test about text.",
            "user": self.user_3,
        }
        self.profile_3 = create_profile(**profile_3_details)

        # create fourth user and profile
        # this profile username should not contain "user"
        user_4_details = {
            "email": "test4@example.com",
            "password": "test-user-password-123",
        }
        self.user_4 = create_user(**user_4_details)
        profile_4_details = {
            "username": "something_different",  # should not container "user"
            "about": "Test about text.",
            "user": self.user_4,
        }
        self.profile_4 = create_profile(**profile_4_details)

        self.client = APIClient()

    def test_search_profiles_without_authentication_returns_error(self):
        """
        Test searching for profiles by username without
        authentication returns error.
        """
        url = search_profiles_url(self.profile.id, "user")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

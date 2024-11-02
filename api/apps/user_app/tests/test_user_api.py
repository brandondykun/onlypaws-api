"""
Tests for the user api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile

MY_INFO_URL = reverse("user_app:my_info")
LOGIN_URL = reverse("user_app:token_obtain_pair")
REFRESH_TOKEN_URL = reverse("user_app:token_refresh")
CREATE_USER_URL = reverse("user_app:create_user")


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


class PublicUserApiTests(TestCase):
    """Test the public features of the User API."""

    def setUp(self):
        self.client = APIClient()

    def test_creates_user_and_profile(self):
        """Returns user info."""
        new_user = {
            "email": "test@example.com",
            "password": "test-user-password-123",
            "username": "test_username",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["email"], new_user["email"])
        self.assertEqual(res.data["profiles"][0]["username"], new_user["username"])

    def test_returns_error_if_no_username(self):
        """Returns error if username is not sent."""
        new_user = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_error_if_no_email(self):
        """Returns error if email is not sent."""
        new_user = {
            "username": "test_username",
            "password": "test-user-password-123",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_error_if_no_password(self):
        """Returns error if password is not sent."""
        new_user = {
            "username": "test_username",
            "email": "test@email.com",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PrivateUserApiTests(TestCase):
    """Test the private features of the User API."""

    def setUp(self):
        user_details = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        self.user = create_user(**user_details)
        profile_details = {
            "username": "test_username",
            "about": "Test about text.",
            "user": self.user,
        }
        self.profile = create_profile(**profile_details)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_returns_info_for_logged_in_user(self):
        """Returns user info."""
        res = self.client.get(MY_INFO_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        expected_info = {
            "id": self.user.id,
            "email": self.user.email,
            "profiles": [
                {
                    "id": self.profile.id,
                    "username": self.profile.username,
                }
            ],
        }
        self.assertEqual(res.data, expected_info)

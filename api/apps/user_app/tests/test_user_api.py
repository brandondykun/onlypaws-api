"""
Tests for the user API (authentication and account management).
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.user_app.models import User
from apps.profile_app.models import Profile
from .util import MY_INFO_URL, CREATE_USER_URL
from core.test_utils.utils import create_user, create_profile


class PublicUserApiTests(TestCase):
    """Test the public features of the User API."""

    def setUp(self):
        self.client = APIClient()

    def test_creates_user_and_profile(self):
        """
        Creating a new user creates a user object but no profile.
        Returns user info with empty profiles list.
        """
        new_user = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["email"], new_user["email"])
        self.assertEqual(res.data["profiles"], [])
        users = User.objects.all()
        profiles = Profile.objects.all()

        self.assertEqual(len(users), 1)
        self.assertEqual(len(profiles), 0)

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
                    "image": None,
                    "name": "",
                    "profile_type": "regular",
                }
            ],
            "is_email_verified": False,
        }
        self.assertEqual(res.data, expected_info)

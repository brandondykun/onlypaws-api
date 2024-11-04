"""
Tests for the user and profile api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, User

MY_INFO_URL = reverse("user_app:my_info")
LOGIN_URL = reverse("user_app:token_obtain_pair")
REFRESH_TOKEN_URL = reverse("user_app:token_refresh")
CREATE_USER_URL = reverse("user_app:create_user")
CREATE_PROFILE_URL = reverse("user_app:create_profile")


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


def retrieve_update_profile_url(profile_id):
    """Create and return a retrieve/update profile url."""
    return reverse("user_app:retrieve_update_profile", args=[profile_id])


class PublicUserApiTests(TestCase):
    """Test the public features of the User API."""

    def setUp(self):
        self.client = APIClient()

    def test_creates_user_and_profile(self):
        """
        Creating a new user creates a user object and profile
        object in database and returns user info.
        """
        new_user = {
            "email": "test@example.com",
            "password": "test-user-password-123",
            "username": "test_username",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["email"], new_user["email"])
        self.assertEqual(res.data["profiles"][0]["username"], new_user["username"])
        users = User.objects.all()
        profiles = Profile.objects.all()

        self.assertEqual(len(users), 1)
        self.assertEqual(len(profiles), 1)

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

    def test_create_new_profile_successful(self):
        """
        Test creating a new profile is successful and creates a new profile object in the
        database that is associated with the authenticated user.
        """
        new_profile = {
            "username": "profile_2",
            "name": "Test Name",
            "about": "Test about text.",
        }
        res = self.client.post(CREATE_PROFILE_URL, new_profile)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["username"], new_profile["username"])
        self.assertEqual(res.data["name"], new_profile["name"])
        self.assertEqual(res.data["about"], new_profile["about"])
        self.assertEqual(res.data["user"], self.user.id)

        profiles = Profile.objects.filter(username=new_profile["username"])
        self.assertEqual(len(profiles), 1)

    def test_update_profile_successful(self):
        """
        Test updating a profile is successful and updates
        the profile object in the database.
        """
        updated_profile = {
            "name": "Updated Name",
            "about": "Updated about text.",
        }
        url = retrieve_update_profile_url(self.profile.id)
        res = self.client.patch(url, updated_profile)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(res.data["id"], self.profile.id)
        self.assertEqual(res.data["username"], self.profile.username)
        self.assertEqual(res.data["name"], updated_profile["name"])
        self.assertEqual(res.data["about"], updated_profile["about"])

        profile = Profile.objects.get(id=self.profile.id)
        self.assertEqual(profile.name, updated_profile["name"])
        self.assertEqual(profile.about, updated_profile["about"])

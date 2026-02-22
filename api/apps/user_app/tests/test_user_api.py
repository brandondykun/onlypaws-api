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

    def test_new_user_has_onboarding_fields_default_to_false(self):
        """Test that new users have onboarding fields defaulting to False."""
        new_user = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        # Check response includes onboarding fields with False values
        self.assertIn("regular_profile_onboarding_completed", res.data)
        self.assertIn("business_profile_onboarding_completed", res.data)
        self.assertFalse(res.data["regular_profile_onboarding_completed"])
        self.assertFalse(res.data["business_profile_onboarding_completed"])
        
        # Verify in database
        user = User.objects.get(email=new_user["email"])
        self.assertFalse(user.regular_profile_onboarding_completed)
        self.assertFalse(user.business_profile_onboarding_completed)

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
                    "public_id": str(self.profile.public_id),
                    "username": self.profile.username,
                    "image": None,
                    "name": "",
                    "profile_type": "regular",
                }
            ],
            "is_email_verified": False,
            "regular_profile_onboarding_completed": False,
            "business_profile_onboarding_completed": False,
        }
        self.assertEqual(res.data, expected_info)

    def test_onboarding_fields_included_in_user_info(self):
        """Test that onboarding fields are included in user info response."""
        res = self.client.get(MY_INFO_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("regular_profile_onboarding_completed", res.data)
        self.assertIn("business_profile_onboarding_completed", res.data)
        self.assertFalse(res.data["regular_profile_onboarding_completed"])
        self.assertFalse(res.data["business_profile_onboarding_completed"])

    def test_onboarding_fields_can_be_updated(self):
        """Test that onboarding fields can be updated and persist."""
        # Initially False
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)
        
        # Update via model
        self.user.regular_profile_onboarding_completed = True
        self.user.business_profile_onboarding_completed = True
        self.user.save()
        
        # Verify update persisted
        self.user.refresh_from_db()
        self.assertTrue(self.user.regular_profile_onboarding_completed)
        self.assertTrue(self.user.business_profile_onboarding_completed)
        
        # Verify in API response
        res = self.client.get(MY_INFO_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["regular_profile_onboarding_completed"])
        self.assertTrue(res.data["business_profile_onboarding_completed"])

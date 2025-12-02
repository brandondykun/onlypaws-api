"""
Tests for profile CRUD API operations.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.profile_app.models import Profile, RegularProfile
from .util import create_profile_url, retrieve_update_profile_url
from core.test_utils.utils import create_user, create_profile


class PrivateProfileApiTests(TestCase):
    """Test the private features of the Profile API."""

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
        res = self.client.post(create_profile_url(), new_profile)
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

        profile = RegularProfile.objects.get(id=self.profile.id)
        self.assertEqual(profile.name, updated_profile["name"])
        self.assertEqual(profile.about, updated_profile["about"])

    def test_create_profile_unauthenticated_fails(self):
        """Test that creating a profile requires authentication."""
        self.client.force_authenticate(user=None)
        new_profile = {
            "username": "unauthenticated_profile",
            "name": "Test Name",
        }
        res = self.client.post(create_profile_url(), new_profile)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_unauthenticated_fails(self):
        """Test that updating a profile requires authentication."""
        self.client.force_authenticate(user=None)
        updated_profile = {"name": "Updated Name"}
        url = retrieve_update_profile_url(self.profile.id)
        res = self.client.patch(url, updated_profile)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_other_user_profile_fails(self):
        """Test that users cannot update profiles they don't own."""
        other_user = create_user(email="other@example.com", password="testpass123")
        other_profile = create_profile(
            user=other_user, 
            username="other_profile",
            about="Test about text."
        )
        
        updated_profile = {"name": "Hacked Name"}
        url = retrieve_update_profile_url(other_profile.id)
        res = self.client.patch(url, updated_profile)
        
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify the profile was not updated
        other_profile.refresh_from_db()
        self.assertNotEqual(other_profile.get_specific_profile().name, "Hacked Name")

    def test_update_username_successful(self):
        """
        Test updating a profile's username is successful and updates
        the profile object in the database.
        """
        updated_profile = {
            "username": "updated_username",
        }
        url = retrieve_update_profile_url(self.profile.id)
        res = self.client.patch(url, updated_profile)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(res.data["id"], self.profile.id)
        self.assertEqual(res.data["username"], updated_profile["username"])
        self.assertEqual(res.data["name"], self.profile.get_specific_profile().name)
        self.assertEqual(res.data["about"], self.profile.get_specific_profile().about)

        profile = RegularProfile.objects.get(id=self.profile.id)
        self.assertEqual(profile.username, updated_profile["username"])

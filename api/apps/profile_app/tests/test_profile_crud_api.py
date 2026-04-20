"""
Tests for profile CRUD API operations.
"""

from unittest.mock import patch

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
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

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
        url = retrieve_update_profile_url(self.profile)
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
        url = retrieve_update_profile_url(self.profile)
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
        url = retrieve_update_profile_url(other_profile)
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
        url = retrieve_update_profile_url(self.profile)
        res = self.client.patch(url, updated_profile)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(res.data["id"], self.profile.id)
        self.assertEqual(res.data["username"], updated_profile["username"])
        self.assertEqual(res.data["name"], self.profile.get_specific_profile().name)
        self.assertEqual(res.data["about"], self.profile.get_specific_profile().about)

        profile = RegularProfile.objects.get(id=self.profile.id)
        self.assertEqual(profile.username, updated_profile["username"])

    @patch("apps.profile_app.serializers.check_and_log_username")
    def test_update_profile_with_profane_username_returns_400(self, mock_check):
        """Test that updating a profile with a profane username returns 400."""
        mock_check.return_value = True
        url = retrieve_update_profile_url(self.profile)
        res = self.client.patch(url, {"username": "badword"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.profile_app.serializers.check_and_log_username")
    def test_update_profile_with_profane_name_returns_400(self, mock_check):
        """Test that updating a profile with a profane name returns 400."""
        mock_check.return_value = True
        url = retrieve_update_profile_url(self.profile)
        res = self.client.patch(url, {"name": "badname"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.profile_app.serializers.check_and_log_text")
    def test_update_profile_with_profane_about_returns_400(self, mock_check):
        """Test that updating a profile with profane about text returns 400."""
        mock_check.return_value = True
        url = retrieve_update_profile_url(self.profile)
        res = self.client.patch(url, {"about": "some bad about text"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.profile_app.serializers.check_and_log_username")
    def test_create_profile_with_profane_username_returns_400(self, mock_check):
        """Test that creating a profile with a profane username returns 400."""
        mock_check.return_value = True
        new_profile = {
            "username": "badusername",
            "name": "Test Name",
            "about": "Test about text.",
        }
        res = self.client.post(create_profile_url(), new_profile)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_profile_returns_title_case_pet_attributes(self):
        """Test that creating a profile returns sex, energy_level, and anxiety_level in title case."""
        new_user = create_user(email="titlecase@example.com", password="testpass123")
        client = APIClient()
        client.force_authenticate(user=new_user)
        new_profile = {
            "username": "tc_pet_attrs",
            "name": "Test Name",
            "sex": "MALE",
            "energy_level": "HIGH",
            "anxiety_level": "LOW",
        }
        res = client.post(create_profile_url(), new_profile)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        # Verify DB stores uppercase
        profile = RegularProfile.objects.get(profile_ptr__username="tc_pet_attrs")
        self.assertEqual(profile.sex, "MALE")
        self.assertEqual(profile.energy_level, "HIGH")
        self.assertEqual(profile.anxiety_level, "LOW")

    def test_update_profile_returns_title_case_pet_attributes(self):
        """Test that updating a profile returns sex, energy_level, and anxiety_level in title case."""
        url = retrieve_update_profile_url(self.profile)
        res = self.client.patch(url, {
            "sex": "FEMALE",
            "energy_level": "MEDIUM",
            "anxiety_level": "HIGH",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["sex"], "Female")
        self.assertEqual(res.data["energy_level"], "Medium")
        self.assertEqual(res.data["anxiety_level"], "High")

        # Verify DB still stores uppercase
        regular_profile = RegularProfile.objects.get(id=self.profile.id)
        self.assertEqual(regular_profile.sex, "FEMALE")
        self.assertEqual(regular_profile.energy_level, "MEDIUM")
        self.assertEqual(regular_profile.anxiety_level, "HIGH")

    def test_update_profile_clears_pet_attributes(self):
        """Test that clearing sex, energy_level, and anxiety_level returns empty strings."""
        # First set values
        url = retrieve_update_profile_url(self.profile)
        self.client.patch(url, {
            "sex": "MALE",
            "energy_level": "LOW",
            "anxiety_level": "MEDIUM",
        })

        # Then clear them
        res = self.client.patch(url, {
            "sex": "",
            "energy_level": "",
            "anxiety_level": "",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["sex"], "")
        self.assertEqual(res.data["energy_level"], "")
        self.assertEqual(res.data["anxiety_level"], "")

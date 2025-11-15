"""
Tests for delete profile API.
"""

import os
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.profile_app.models import Profile, ProfileImage

from .util import get_profile_detail_url
from core.test_utils.utils import create_user, create_profile, create_profile_image


class DeleteProfileAPITests(TestCase):
    """Test the delete profile API."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="user@example.com", password="testpass123")
        self.profile1 = create_profile(user=self.user, username="profile1")
        self.profile2 = create_profile(user=self.user, username="profile2")
        self.client.force_authenticate(user=self.user)

    def test_delete_profile_success(self):
        """Test deleting a profile successfully."""
        url = get_profile_detail_url(self.profile2.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profile.objects.filter(id=self.profile2.id).exists())
        self.assertTrue(Profile.objects.filter(id=self.profile1.id).exists())

    def test_delete_profile_with_image(self):
        """Test deleting a profile that has an associated image."""
        profile_image = create_profile_image(self.profile2)
        image_path = profile_image.image.path
        url = get_profile_detail_url(self.profile2.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profile.objects.filter(id=self.profile2.id).exists())
        self.assertFalse(ProfileImage.objects.filter(profile=self.profile2).exists())
        self.assertFalse(os.path.exists(image_path))

    def test_delete_last_profile_fails(self):
        """Test attempting to delete the user's last profile."""
        # Delete profile2 first
        Profile.objects.filter(id=self.profile2.id).delete()
        url = get_profile_detail_url(self.profile1.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot delete your only profile", str(res.data["error"]))
        self.assertTrue(Profile.objects.filter(id=self.profile1.id).exists())

    def test_delete_other_user_profile_fails(self):
        """Test attempting to delete another user's profile."""
        other_user = create_user(email="other@example.com")
        other_profile = create_profile(user=other_user, username="otheruser")
        url = get_profile_detail_url(other_profile.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Profile not found", str(res.data["error"]))
        self.assertTrue(Profile.objects.filter(id=other_profile.id).exists())

    def test_delete_nonexistent_profile(self):
        """Test attempting to delete a profile that doesn't exist."""
        url = get_profile_detail_url(99999)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Profile not found", str(res.data["error"]))

    def test_delete_profile_unauthenticated(self):
        """Test attempting to delete a profile while not authenticated."""
        self.client.force_authenticate(user=None)
        url = get_profile_detail_url(self.profile1.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Profile.objects.filter(id=self.profile1.id).exists())


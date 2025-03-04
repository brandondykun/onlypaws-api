"""
Tests for the change password API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status


CHANGE_PASSWORD_URL = reverse("user_app:change_password")


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)


class PublicChangePasswordAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.patch(CHANGE_PASSWORD_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateChangePasswordAPITests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        """Test changing password with valid data."""
        payload = {
            "old_password": "testpass123",
            "new_password": "newtestpass123",
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload["new_password"]))

    def test_change_password_wrong_old_password(self):
        """Test changing password with wrong old password."""
        payload = {
            "old_password": "wrongpass123",
            "new_password": "newtestpass123",
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", res.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(payload["new_password"]))
        self.assertTrue(self.user.check_password("testpass123"))

    def test_change_password_same_password(self):
        """Test changing password to the same password."""
        payload = {
            "old_password": "testpass123",
            "new_password": "testpass123",
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)

    def test_change_password_invalid_new_password(self):
        """Test changing password with invalid new password."""
        payload = {
            "old_password": "testpass123",
            "new_password": "short",  # Too short
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

    def test_change_password_missing_fields(self):
        """Test changing password with missing fields."""
        # Test missing old password
        payload1 = {"new_password": "newtestpass123"}
        res1 = self.client.patch(CHANGE_PASSWORD_URL, payload1)
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", res1.data)

        # Test missing new password
        payload2 = {"old_password": "testpass123"}
        res2 = self.client.patch(CHANGE_PASSWORD_URL, payload2)
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res2.data)

    def test_change_password_empty_fields(self):
        """Test changing password with empty fields."""
        payload = {
            "old_password": "",
            "new_password": "",
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", res.data)
        self.assertIn("new_password", res.data)

    def test_change_password_common_password(self):
        """Test changing password to a common password."""
        payload = {
            "old_password": "testpass123",
            "new_password": "password123",  # Common password
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

    def test_change_password_numeric_only(self):
        """Test changing password to numeric only password."""
        payload = {
            "old_password": "testpass123",
            "new_password": "123456789",  # Numeric only
        }

        res = self.client.patch(CHANGE_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

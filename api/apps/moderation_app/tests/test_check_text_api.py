"""
Tests for the CheckTextView API endpoint.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile


CHECK_TEXT_URL = reverse("moderation_app:check-text")


class PublicCheckTextTests(TestCase):
    """Tests for unauthenticated access to the check text endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(CHECK_TEXT_URL, {"text": "hello"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateCheckTextTests(TestCase):
    """Tests for authenticated access to the check text endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user("checktext@example.com", "password123")
        self.profile = create_profile("checktext_user", self.user)
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    @patch("apps.moderation_app.views.check_and_log_text")
    def test_clean_text_returns_allowed(self, mock_check):
        """Test that clean text returns allowed=True."""
        mock_check.return_value = False
        response = self.client.post(CHECK_TEXT_URL, {"text": "hello"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["allowed"])

    @patch("apps.moderation_app.views.check_and_log_text")
    def test_profane_text_returns_not_allowed(self, mock_check):
        """Test that profane text returns allowed=False with a message."""
        mock_check.return_value = True
        response = self.client.post(CHECK_TEXT_URL, {"text": "bad word"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["allowed"])
        self.assertEqual(
            response.data["message"],
            "That text contains inappropriate language.",
        )

    def test_empty_text_returns_allowed(self):
        """Test that empty text returns allowed=True without calling profanity service."""
        response = self.client.post(CHECK_TEXT_URL, {"text": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["allowed"])

    def test_missing_text_returns_allowed(self):
        """Test that missing text field returns allowed=True."""
        response = self.client.post(CHECK_TEXT_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["allowed"])

    @patch("apps.moderation_app.views.check_and_log_text")
    def test_check_text_calls_service_with_correct_args(self, mock_check):
        """Test that the profanity service is called with correct arguments."""
        mock_check.return_value = False
        self.client.post(CHECK_TEXT_URL, {"text": "some text"}, format="json")

        mock_check.assert_called_once_with(
            "some text", "PRE_UPLOAD_CHECK", profile_id=self.profile.id
        )

    def test_only_post_method_allowed(self):
        """Test that only POST method is allowed."""
        # GET
        response = self.client.get(CHECK_TEXT_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(CHECK_TEXT_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(CHECK_TEXT_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(CHECK_TEXT_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_without_profile_header_returns_401(self):
        """Test that the endpoint returns 401 without profile header due to middleware."""
        # Remove profile header — middleware requires it for authenticated API requests
        self.client.credentials()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(CHECK_TEXT_URL, {"text": "hello"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

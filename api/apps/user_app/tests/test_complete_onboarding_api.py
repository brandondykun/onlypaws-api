"""
Tests for the complete onboarding API endpoint.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .util import COMPLETE_ONBOARDING_URL
from core.test_utils.utils import create_user


class PublicCompleteOnboardingAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.post(COMPLETE_ONBOARDING_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateCompleteOnboardingAPITests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_complete_regular_profile_onboarding_success(self):
        """Test completing regular profile onboarding with valid data."""
        payload = {
            "profile_type": "regular",
        }

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("message", res.data)
        self.assertIn("user", res.data)
        self.assertEqual(
            res.data["message"], "Regular profile onboarding marked as complete."
        )
        
        # Verify user was updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)
        
        # Verify user data in response
        self.assertTrue(res.data["user"]["regular_profile_onboarding_completed"])
        self.assertFalse(res.data["user"]["business_profile_onboarding_completed"])

    def test_complete_business_profile_onboarding_success(self):
        """Test completing business profile onboarding with valid data."""
        payload = {
            "profile_type": "business",
        }

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("message", res.data)
        self.assertIn("user", res.data)
        self.assertEqual(
            res.data["message"], "Business profile onboarding marked as complete."
        )
        
        # Verify user was updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertTrue(self.user.business_profile_onboarding_completed)
        
        # Verify user data in response
        self.assertFalse(res.data["user"]["regular_profile_onboarding_completed"])
        self.assertTrue(res.data["user"]["business_profile_onboarding_completed"])

    def test_complete_both_profile_onboardings(self):
        """Test completing both regular and business profile onboardings."""
        # Complete regular onboarding first
        payload1 = {"profile_type": "regular"}
        res1 = self.client.post(COMPLETE_ONBOARDING_URL, payload1)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        
        # Complete business onboarding
        payload2 = {"profile_type": "business"}
        res2 = self.client.post(COMPLETE_ONBOARDING_URL, payload2)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        
        # Verify both are completed
        self.user.refresh_from_db()
        self.assertTrue(self.user.regular_profile_onboarding_completed)
        self.assertTrue(self.user.business_profile_onboarding_completed)

    def test_complete_onboarding_invalid_profile_type(self):
        """Test completing onboarding with invalid profile_type."""
        payload = {
            "profile_type": "invalid",
        }

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profile_type", res.data)
        
        # Verify user was not updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)

    def test_complete_onboarding_missing_profile_type(self):
        """Test completing onboarding with missing profile_type."""
        payload = {}

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profile_type", res.data)
        
        # Verify user was not updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)

    def test_complete_onboarding_empty_profile_type(self):
        """Test completing onboarding with empty profile_type."""
        payload = {
            "profile_type": "",
        }

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profile_type", res.data)
        
        # Verify user was not updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)

    def test_complete_onboarding_case_sensitive(self):
        """Test that profile_type is case sensitive."""
        payload = {
            "profile_type": "Regular",  # Capitalized
        }

        res = self.client.post(COMPLETE_ONBOARDING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profile_type", res.data)
        
        # Verify user was not updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.regular_profile_onboarding_completed)
        self.assertFalse(self.user.business_profile_onboarding_completed)

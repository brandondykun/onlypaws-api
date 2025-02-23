"""
Tests for the password reset API endpoints.
"""

from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import ResetPasswordToken

REQUEST_RESET_URL = reverse("user_app:request_password_reset")
RESET_PASSWORD_URL = reverse("user_app:reset_password")


class PasswordResetApiTests(TestCase):
    """Test the password reset API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_request_reset_token_success(self):
        """Test requesting password reset token is successful."""
        payload = {"email": self.user.email}
        res = self.client.post(REQUEST_RESET_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data["message"],
            "If a user with this email exists, they will receive a reset code.",
        )
        self.assertTrue(ResetPasswordToken.objects.filter(user=self.user).exists())

    def test_request_reset_token_nonexistent_email(self):
        """Test requesting reset token for nonexistent email returns success
        (to prevent email enumeration)."""
        payload = {"email": "nonexistent@example.com"}
        res = self.client.post(REQUEST_RESET_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data["message"],
            "If a user with this email exists, they will receive a reset code.",
        )
        self.assertFalse(
            ResetPasswordToken.objects.filter(
                user__email="nonexistent@example.com"
            ).exists()
        )

    def test_request_reset_token_missing_email(self):
        """Test error returned if email is missing."""
        res = self.client.post(REQUEST_RESET_URL, {})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Email is required")

    def test_request_reset_token_replaces_existing(self):
        """Test requesting new token replaces existing one."""
        # Create initial token
        payload = {"email": self.user.email}
        self.client.post(REQUEST_RESET_URL, payload)
        original_token = ResetPasswordToken.objects.get(user=self.user)

        # Request new token
        self.client.post(REQUEST_RESET_URL, payload)
        new_token = ResetPasswordToken.objects.get(user=self.user)

        self.assertNotEqual(original_token.token, new_token.token)
        self.assertEqual(ResetPasswordToken.objects.count(), 1)

    def test_reset_password_success(self):
        """Test successful password reset."""
        # Create reset token
        self.client.post(REQUEST_RESET_URL, {"email": self.user.email})
        token = ResetPasswordToken.objects.get(user=self.user)

        # Reset password
        payload = {
            "email": self.user.email,
            "token": token.token,
            "password": "newpass123",
        }
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["message"], "Password reset successful")

        # Verify token is deleted
        self.assertFalse(ResetPasswordToken.objects.filter(user=self.user).exists())

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_reset_password_invalid_token(self):
        """Test reset password with invalid token fails."""
        payload = {
            "email": self.user.email,
            "token": "invalid_token",
            "password": "newpass123",
        }
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Invalid confirmation code")

        # Verify password was not changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

    def test_reset_password_expired_token(self):
        """Test reset password with expired token fails."""
        # Create reset token
        self.client.post(REQUEST_RESET_URL, {"email": self.user.email})
        token = ResetPasswordToken.objects.get(user=self.user)

        # Expire token
        token.created_at = timezone.now() - timedelta(minutes=16)
        token.save()

        payload = {
            "email": self.user.email,
            "token": token.token,
            "password": "newpass123",
        }
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Reset token has expired")

        # Verify token was deleted
        self.assertFalse(ResetPasswordToken.objects.filter(user=self.user).exists())

        # Verify password was not changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

    def test_reset_password_missing_fields(self):
        """Test reset password with missing fields fails."""
        # Test missing email
        res = self.client.post(
            RESET_PASSWORD_URL,
            {"token": "token", "password": "newpass123"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Test missing token
        res = self.client.post(
            RESET_PASSWORD_URL,
            {"email": self.user.email, "password": "newpass123"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Test missing password
        res = self.client.post(
            RESET_PASSWORD_URL,
            {"email": self.user.email, "token": "token"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_nonexistent_email(self):
        """Test reset password with nonexistent email fails."""
        payload = {
            "email": "nonexistent@example.com",
            "token": "token",
            "password": "newpass123",
        }
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Invalid confirmation code")

    def test_reset_password_weak_password(self):
        """Test reset password with weak password fails."""
        # Create reset token
        self.client.post(REQUEST_RESET_URL, {"email": self.user.email})
        token = ResetPasswordToken.objects.get(user=self.user)

        # Try to reset with weak password
        payload = {
            "email": self.user.email,
            "token": token.token,
            "password": "weak",
        }
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)  # Exact message depends on validator

        # Verify password was not changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

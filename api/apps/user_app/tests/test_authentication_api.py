"""
Tests for the JWT authentication API endpoints.

This module tests the custom JWT authentication views that handle
dual-client support (mobile + web) with different token delivery methods.
"""

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)

from core.test_utils.utils import create_user


# URL Constants
LOGIN_URL = reverse("user_app:token_obtain_pair")
REFRESH_URL = reverse("user_app:token_refresh")
LOGOUT_URL = reverse("user_app:logout")
LOGOUT_ALL_URL = reverse("user_app:logout_all")

# Cookie name from settings
REFRESH_COOKIE_NAME = "refresh_token"


class LoginMobileClientTests(TestCase):
    """Tests for mobile client login (tokens in response body)."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("mobile@example.com", self.password)

    def test_mobile_login_returns_both_tokens_in_body(self):
        """Test that mobile client receives both access and refresh tokens in body."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        # No cookie should be set for mobile clients
        self.assertNotIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_login_without_client_type_header_defaults_to_mobile(self):
        """Test that missing X-Client-Type header defaults to mobile behavior."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_login_with_invalid_client_type_defaults_to_mobile(self):
        """Test that invalid X-Client-Type header defaults to mobile behavior."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="invalid_type",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class LoginWebClientTests(TestCase):
    """Tests for web client login (refresh token in HttpOnly cookie)."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("web@example.com", self.password)

    def test_web_login_returns_access_in_body_refresh_in_cookie(self):
        """Test that web client receives access token in body and refresh in cookie."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)
        
        cookie = response.cookies[REFRESH_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])

    def test_web_login_case_insensitive_header(self):
        """Test that X-Client-Type header is case-insensitive."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="WEB",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)


class LoginErrorTests(TestCase):
    """Tests for login error cases."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("test@example.com", self.password)

    def test_login_with_invalid_password_returns_401(self):
        """Test that login with incorrect password returns 401."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_login_with_invalid_email_returns_401(self):
        """Test that login with non-existent email returns 401."""
        response = self.client.post(
            LOGIN_URL,
            {"email": "nonexistent@example.com", "password": self.password},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_missing_email_returns_400(self):
        """Test that login without email returns 400."""
        response = self.client.post(
            LOGIN_URL,
            {"password": self.password},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_missing_password_returns_400(self):
        """Test that login without password returns 400."""
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_empty_body_returns_400(self):
        """Test that login with empty body returns 400."""
        response = self.client.post(LOGIN_URL, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_inactive_user_returns_401(self):
        """Test that login with inactive user returns 401."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RefreshMobileClientTests(TestCase):
    """Tests for mobile client token refresh (token in body)."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("mobile@example.com", self.password)
        self.refresh_token = RefreshToken.for_user(self.user)

    def test_mobile_refresh_returns_both_tokens_in_body(self):
        """Test that mobile client receives new access and refresh tokens in body."""
        response = self.client.post(
            REFRESH_URL,
            {"refresh": str(self.refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        # New refresh token should be different due to rotation
        self.assertNotEqual(response.data["refresh"], str(self.refresh_token))

    def test_refresh_without_client_type_defaults_to_mobile(self):
        """Test that refresh without X-Client-Type defaults to mobile behavior."""
        response = self.client.post(
            REFRESH_URL,
            {"refresh": str(self.refresh_token)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class RefreshWebClientTests(TestCase):
    """Tests for web client token refresh (token from cookie)."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("web@example.com", self.password)

    def test_web_refresh_uses_cookie_returns_access_in_body(self):
        """Test that web client can refresh using cookie and gets new cookie."""
        # First login to get the cookie
        login_response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="web",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        
        # Extract cookie value and set it on the client
        refresh_cookie = login_response.cookies[REFRESH_COOKIE_NAME].value
        self.client.cookies[REFRESH_COOKIE_NAME] = refresh_cookie

        # Refresh using the cookie
        response = self.client.post(
            REFRESH_URL,
            {},  # No body needed for web client
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_web_refresh_with_token_in_body_also_works(self):
        """Test that web client can also refresh by sending token in body."""
        refresh_token = RefreshToken.for_user(self.user)

        response = self.client.post(
            REFRESH_URL,
            {"refresh": str(refresh_token)},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)


class RefreshErrorTests(TestCase):
    """Tests for token refresh error cases."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("test@example.com", self.password)

    def test_refresh_with_missing_token_returns_400(self):
        """Test that refresh without token returns 400."""
        response = self.client.post(
            REFRESH_URL,
            {},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_refresh_with_invalid_token_returns_401(self):
        """Test that refresh with invalid token returns 401."""
        response = self.client.post(
            REFRESH_URL,
            {"refresh": "invalid-token"},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_with_blacklisted_token_returns_401(self):
        """Test that refresh with blacklisted token returns 401."""
        refresh_token = RefreshToken.for_user(self.user)
        refresh_token.blacklist()

        response = self.client.post(
            REFRESH_URL,
            {"refresh": str(refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_with_expired_token_returns_401(self):
        """Test that refresh with malformed token returns 401."""
        # Simulate an expired/corrupted token by using a mangled token string
        refresh_token = RefreshToken.for_user(self.user)
        mangled_token = str(refresh_token)[:-10] + "corrupted!"

        response = self.client.post(
            REFRESH_URL,
            {"refresh": mangled_token},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_web_refresh_without_cookie_or_body_returns_400(self):
        """Test that web client refresh without cookie or body returns 400."""
        response = self.client.post(
            REFRESH_URL,
            {},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRotationTests(TestCase):
    """Tests for token rotation behavior."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("rotation@example.com", self.password)

    def test_refresh_rotates_token(self):
        """Test that refreshing creates a new refresh token."""
        refresh_token = RefreshToken.for_user(self.user)
        old_token_str = str(refresh_token)

        response = self.client.post(
            REFRESH_URL,
            {"refresh": old_token_str},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_token_str = response.data["refresh"]
        self.assertNotEqual(old_token_str, new_token_str)

    def test_old_token_blacklisted_after_rotation(self):
        """Test that old token is blacklisted after rotation."""
        refresh_token = RefreshToken.for_user(self.user)
        old_token_str = str(refresh_token)

        # First refresh
        response = self.client.post(
            REFRESH_URL,
            {"refresh": old_token_str},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to use the old token again
        response = self.client.post(
            REFRESH_URL,
            {"refresh": old_token_str},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_token_works_after_rotation(self):
        """Test that new token from rotation works for subsequent refreshes."""
        refresh_token = RefreshToken.for_user(self.user)

        # First refresh
        response1 = self.client.post(
            REFRESH_URL,
            {"refresh": str(refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        new_token = response1.data["refresh"]

        # Second refresh with new token
        response2 = self.client.post(
            REFRESH_URL,
            {"refresh": new_token},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)


class LogoutMobileClientTests(TestCase):
    """Tests for mobile client logout."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("mobile@example.com", self.password)
        self.refresh_token = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)

    def test_mobile_logout_blacklists_token(self):
        """Test that mobile logout blacklists the refresh token."""
        response = self.client.post(
            LOGOUT_URL,
            {"refresh": str(self.refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Successfully logged out")

        # Verify token is blacklisted
        blacklisted = BlacklistedToken.objects.filter(
            token__token=str(self.refresh_token)
        ).exists()
        self.assertTrue(blacklisted)

    def test_mobile_logout_token_cannot_be_reused(self):
        """Test that blacklisted token cannot be used for refresh."""
        # Logout
        self.client.post(
            LOGOUT_URL,
            {"refresh": str(self.refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        # Try to refresh with blacklisted token
        self.client.force_authenticate(user=None)  # Remove auth for refresh
        response = self.client.post(
            REFRESH_URL,
            {"refresh": str(self.refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutWebClientTests(TestCase):
    """Tests for web client logout."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("web@example.com", self.password)
        self.client.force_authenticate(user=self.user)

    def test_web_logout_uses_cookie_and_deletes_it(self):
        """Test that web logout uses cookie and deletes it."""
        # Login to get cookie
        self.client.force_authenticate(user=None)
        login_response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="web",
        )
        refresh_cookie = login_response.cookies[REFRESH_COOKIE_NAME].value
        self.client.cookies[REFRESH_COOKIE_NAME] = refresh_cookie
        
        # Re-authenticate for logout (requires authentication)
        self.client.force_authenticate(user=self.user)

        # Logout
        response = self.client.post(
            LOGOUT_URL,
            {},  # No body needed for web client
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cookie should be deleted (set with empty value or max_age=0)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_web_logout_with_token_in_body_also_works(self):
        """Test that web client can also logout by sending token in body."""
        refresh_token = RefreshToken.for_user(self.user)

        response = self.client.post(
            LOGOUT_URL,
            {"refresh": str(refresh_token)},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cookie deletion header should still be set for web clients
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)


class LogoutErrorTests(TestCase):
    """Tests for logout error cases."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("test@example.com", self.password)

    def test_logout_unauthenticated_returns_401(self):
        """Test that logout without authentication returns 401."""
        refresh_token = RefreshToken.for_user(self.user)

        response = self.client.post(
            LOGOUT_URL,
            {"refresh": str(refresh_token)},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_token_returns_400(self):
        """Test that logout without refresh token returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            LOGOUT_URL,
            {},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_logout_with_invalid_token_returns_400(self):
        """Test that logout with invalid token returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            LOGOUT_URL,
            {"refresh": "invalid-token"},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_logout_with_already_blacklisted_token_returns_400(self):
        """Test that logout with already blacklisted token returns 400."""
        self.client.force_authenticate(user=self.user)
        refresh_token = RefreshToken.for_user(self.user)
        refresh_token.blacklist()

        response = self.client.post(
            LOGOUT_URL,
            {"refresh": str(refresh_token)},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_web_logout_invalid_token_still_deletes_cookie(self):
        """Test that web logout with invalid token still deletes the cookie."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            LOGOUT_URL,
            {"refresh": "invalid-token"},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Cookie should still be deleted even on error for web clients
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)


class LogoutAllMobileClientTests(TestCase):
    """Tests for mobile client logout from all devices."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("mobile@example.com", self.password)
        self.client.force_authenticate(user=self.user)

    def test_logout_all_blacklists_all_tokens(self):
        """Test that logout-all blacklists all outstanding tokens."""
        # Create multiple refresh tokens (simulating multiple devices)
        token1 = RefreshToken.for_user(self.user)
        token2 = RefreshToken.for_user(self.user)
        token3 = RefreshToken.for_user(self.user)

        outstanding_count = OutstandingToken.objects.filter(user=self.user).count()
        self.assertGreaterEqual(outstanding_count, 3)

        response = self.client.post(
            LOGOUT_ALL_URL,
            {},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"], "Successfully logged out from all devices"
        )
        self.assertIn("sessions_terminated", response.data)
        self.assertGreaterEqual(response.data["sessions_terminated"], 3)

        # Verify all tokens are blacklisted
        blacklisted_count = BlacklistedToken.objects.filter(
            token__user=self.user
        ).count()
        self.assertEqual(blacklisted_count, outstanding_count)

    def test_logout_all_tokens_cannot_be_reused(self):
        """Test that no token can be used after logout-all."""
        token1 = RefreshToken.for_user(self.user)
        token2 = RefreshToken.for_user(self.user)

        # Logout all
        self.client.post(LOGOUT_ALL_URL, {}, HTTP_X_CLIENT_TYPE="mobile")

        # Try to use tokens
        self.client.force_authenticate(user=None)
        
        response1 = self.client.post(
            REFRESH_URL,
            {"refresh": str(token1)},
        )
        self.assertEqual(response1.status_code, status.HTTP_401_UNAUTHORIZED)

        response2 = self.client.post(
            REFRESH_URL,
            {"refresh": str(token2)},
        )
        self.assertEqual(response2.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutAllWebClientTests(TestCase):
    """Tests for web client logout from all devices."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("web@example.com", self.password)
        self.client.force_authenticate(user=self.user)

    def test_web_logout_all_deletes_cookie(self):
        """Test that web logout-all deletes the refresh cookie."""
        # Create some tokens
        RefreshToken.for_user(self.user)
        RefreshToken.for_user(self.user)

        response = self.client.post(
            LOGOUT_ALL_URL,
            {},
            HTTP_X_CLIENT_TYPE="web",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cookie deletion header should be set
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)


class LogoutAllErrorTests(TestCase):
    """Tests for logout-all error cases."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("test@example.com", self.password)

    def test_logout_all_unauthenticated_returns_401(self):
        """Test that logout-all without authentication returns 401."""
        response = self.client.post(LOGOUT_ALL_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_all_with_no_outstanding_tokens(self):
        """Test logout-all when user has no outstanding tokens."""
        self.client.force_authenticate(user=self.user)

        # Clear any existing tokens
        OutstandingToken.objects.filter(user=self.user).delete()

        response = self.client.post(LOGOUT_ALL_URL, {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sessions_terminated"], 0)


class AuthenticationFlowTests(TestCase):
    """Integration tests for complete authentication flows."""

    def setUp(self):
        self.client = APIClient()
        self.password = "secure-password-123"
        self.user = create_user("flow@example.com", self.password)

    def test_complete_mobile_auth_flow(self):
        """Test complete mobile authentication flow: login -> refresh -> logout."""
        # Login
        login_response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        access_token = login_response.data["access"]
        refresh_token = login_response.data["refresh"]

        # Use access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        
        # Refresh
        refresh_response = self.client.post(
            REFRESH_URL,
            {"refresh": refresh_token},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_refresh_token = refresh_response.data["refresh"]

        # Logout with new refresh token
        logout_response = self.client.post(
            LOGOUT_URL,
            {"refresh": new_refresh_token},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Verify old token is blacklisted (from rotation)
        self.client.credentials()  # Clear auth
        old_refresh_response = self.client.post(
            REFRESH_URL,
            {"refresh": refresh_token},
        )
        self.assertEqual(old_refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_complete_web_auth_flow(self):
        """Test complete web authentication flow: login -> refresh -> logout."""
        # Login
        login_response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="web",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertNotIn("refresh", login_response.data)
        
        # Extract and set cookie
        refresh_cookie = login_response.cookies[REFRESH_COOKIE_NAME].value
        self.client.cookies[REFRESH_COOKIE_NAME] = refresh_cookie
        access_token = login_response.data["access"]

        # Refresh using cookie
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        refresh_response = self.client.post(
            REFRESH_URL,
            {},
            HTTP_X_CLIENT_TYPE="web",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)
        self.assertNotIn("refresh", refresh_response.data)

        # Update cookie with new refresh token
        new_refresh_cookie = refresh_response.cookies[REFRESH_COOKIE_NAME].value
        self.client.cookies[REFRESH_COOKIE_NAME] = new_refresh_cookie

        # Logout
        logout_response = self.client.post(
            LOGOUT_URL,
            {},
            HTTP_X_CLIENT_TYPE="web",
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

    def test_multiple_device_login_and_selective_logout(self):
        """Test that logging in from multiple devices creates separate sessions."""
        # Login from "device 1"
        login1 = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        refresh1 = login1.data["refresh"]

        # Login from "device 2"
        login2 = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.password},
            HTTP_X_CLIENT_TYPE="mobile",
        )
        refresh2 = login2.data["refresh"]

        # Tokens should be different
        self.assertNotEqual(refresh1, refresh2)

        # Logout from device 1
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login1.data['access']}")
        self.client.post(
            LOGOUT_URL,
            {"refresh": refresh1},
            HTTP_X_CLIENT_TYPE="mobile",
        )

        # Device 1 token should be blacklisted
        self.client.credentials()
        response1 = self.client.post(
            REFRESH_URL,
            {"refresh": refresh1},
        )
        self.assertEqual(response1.status_code, status.HTTP_401_UNAUTHORIZED)

        # Device 2 token should still work
        response2 = self.client.post(
            REFRESH_URL,
            {"refresh": refresh2},
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_logout_all_terminates_all_sessions(self):
        """Test that logout-all terminates sessions on all devices."""
        # Login from multiple "devices"
        tokens = []
        for i in range(3):
            login = self.client.post(
                LOGIN_URL,
                {"email": self.user.email, "password": self.password},
                HTTP_X_CLIENT_TYPE="mobile",
            )
            tokens.append(login.data["refresh"])

        # Verify all tokens work
        for token in tokens:
            response = self.client.post(
                REFRESH_URL,
                {"refresh": token},
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Logout all using the last login's access token
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )
        self.client.post(LOGOUT_ALL_URL, {})

        # All tokens should now be blacklisted
        self.client.credentials()
        for token in tokens:
            response = self.client.post(
                REFRESH_URL,
                {"refresh": token},
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

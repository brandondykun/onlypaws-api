"""
Tests for the email verification API endpoints.
"""

from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import VerifyEmailToken

CREATE_USER_URL = reverse("user_app:create_user")
VERIFY_EMAIL_URL = reverse("user_app:verify_email_token")
REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL = reverse("user_app:request_new_verify_email_token")


class EmailVerificationApiTests(TestCase):
    """Test the email verification API endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_create_new_profile_creates_verify_email_token(self):
        """Creating a new user also creates a verify email token."""
        new_user = {
            "email": "test@example2.com",
            "password": "test-user-password-123",
            "username": "test_username_2",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["email"], new_user["email"])
        self.assertEqual(res.data["profiles"][0]["username"], new_user["username"])

        users_filtered = get_user_model().objects.filter(id=res.data["id"])
        new_user = users_filtered[0]
        self.assertEqual(new_user.is_email_verified, False)

        verify_email_tokens = VerifyEmailToken.objects.all()
        self.assertEqual(len(verify_email_tokens), 1)

        token = verify_email_tokens.first()
        self.assertEqual(token.user, users_filtered.first())

    def test_create_new_profile_verify_email_successful(self):
        """
        Creating a new user sets is_email_verified to False.
        Verifying the email sets is_email_verified to True.
        """
        # create new user
        new_user = {
            "email": "test@example3.com",
            "password": "test-user-password-123",
            "username": "test_username_3",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # assert user created with initial is_email_verified set to false
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.assertEqual(new_user.is_email_verified, False)

        # authenticate as new user
        self.client.force_authenticate(user=new_user)

        # verify email
        verify_email_token = VerifyEmailToken.objects.get(user=new_user)
        data = {"token": verify_email_token.token}
        self.client.post(VERIFY_EMAIL_URL, data)

        # assert email was verified
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.assertEqual(new_user.is_email_verified, True)

        # assert token was deleted
        filtered_tokens = VerifyEmailToken.objects.filter(user=new_user)
        self.assertEqual(len(filtered_tokens), 0)

        # try to reverify email returns error
        reverify_res = self.client.post(VERIFY_EMAIL_URL, data)
        self.assertEqual(reverify_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_email_invalid_token(self):
        """Test verifying email with invalid token returns error."""
        # create new user
        new_user = {
            "email": "test@example4.com",
            "password": "test-user-password-123",
            "username": "test_username_4",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # verify with invalid token
        data = {"token": "invalid_token"}
        res = self.client.post(VERIFY_EMAIL_URL, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Invalid verification code")

        # assert email still not verified
        new_user.refresh_from_db()
        self.assertEqual(new_user.is_email_verified, False)

    def test_verify_email_missing_token(self):
        """Test verifying email without token returns error."""
        # create new user
        new_user = {
            "email": "test@example5.com",
            "password": "test-user-password-123",
            "username": "test_username_5",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # verify without token
        data = {}
        res = self.client.post(VERIFY_EMAIL_URL, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Verification token is required")

    def test_verify_email_expired_token(self):
        """Test verifying email with expired token returns error."""
        # create new user
        new_user = {
            "email": "test@example6.com",
            "password": "test-user-password-123",
            "username": "test_username_6",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # get token and modify created_at to be expired
        verify_email_token = VerifyEmailToken.objects.get(user=new_user)
        verify_email_token.created_at = timezone.now() - timedelta(minutes=11)
        verify_email_token.save()

        # verify with expired token
        data = {"token": verify_email_token.token}
        res = self.client.post(VERIFY_EMAIL_URL, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Verification code has expired")

        # assert email still not verified
        new_user.refresh_from_db()
        self.assertEqual(new_user.is_email_verified, False)

    def test_verify_email_no_token_exists(self):
        """Test verifying email when no token exists returns error."""
        # create new user
        new_user = {
            "email": "test@example7.com",
            "password": "test-user-password-123",
            "username": "test_username_7",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # delete token
        VerifyEmailToken.objects.filter(user=new_user).delete()

        # attempt to verify
        data = {"token": "any_token"}
        res = self.client.post(VERIFY_EMAIL_URL, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "No verification token found")

    def test_request_new_verify_email_token_success(self):
        """Test requesting new verification token is successful."""
        # create new user
        new_user = {
            "email": "test@example8.com",
            "password": "test-user-password-123",
            "username": "test_username_8",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # delete existing token
        VerifyEmailToken.objects.filter(user=new_user).delete()

        # request new token
        res = self.client.post(REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["message"], "Verification token sent.")

        # verify new token was created
        self.assertTrue(VerifyEmailToken.objects.filter(user=new_user).exists())

    def test_request_new_verify_email_token_already_verified(self):
        """Test requesting new token when email already verified returns error."""
        # create new user
        new_user = {
            "email": "test@example9.com",
            "password": "test-user-password-123",
            "username": "test_username_9",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # mark email as verified
        new_user.is_email_verified = True
        new_user.save()

        # request new token
        res = self.client.post(REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Email already verified")

    def test_request_new_verify_email_token_replaces_existing(self):
        """Test requesting new token deletes existing token and creates new one."""
        # create new user
        new_user = {
            "email": "test@example10.com",
            "password": "test-user-password-123",
            "username": "test_username_10",
        }
        res = self.client.post(CREATE_USER_URL, new_user)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # authenticate as new user
        new_user = get_user_model().objects.get(id=res.data["id"])
        self.client.force_authenticate(user=new_user)

        # get original token
        original_token = VerifyEmailToken.objects.get(user=new_user)

        # request new token
        res = self.client.post(REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # verify new token was created and is different
        new_token = VerifyEmailToken.objects.get(user=new_user)
        self.assertNotEqual(original_token.token, new_token.token)

    def test_request_new_verify_email_token_unauthenticated(self):
        """Test requesting new token when not authenticated fails."""
        self.client.force_authenticate(user=None)
        res = self.client.post(REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

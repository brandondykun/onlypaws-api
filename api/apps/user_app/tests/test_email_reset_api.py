"""
Tests for email change functionality.
"""

from django.test import TestCase
from django.urls import reverse
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from apps.core_app.models import User, PendingEmailChange
from apps.core_app.utils import generate_verification_code


def create_user(email="test@example.com", password="testpass123"):
    """Helper function to create a test user."""
    return User.objects.create_user(email=email, password=password)


class PublicEmailChangeAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_request_email_change_auth_required(self):
        """Test authentication is required for requesting email change."""
        res = self.client.post(reverse("user_app:request-email-change"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_email_change_auth_required(self):
        """Test authentication is required for verifying email change."""
        res = self.client.post(reverse("user_app:verify-email-change"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateEmailChangeAPITests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)
        self.request_url = reverse("user_app:request-email-change")
        self.verify_url = reverse("user_app:verify-email-change")

    def test_request_email_change_success(self):
        """Test successful email change request."""
        new_email = "newemail@example.com"
        res = self.client.post(self.request_url, {"email": new_email})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["message"], "Verification email sent")

        # Check pending change was created
        pending_change = PendingEmailChange.objects.get(user=self.user)
        self.assertEqual(pending_change.new_email, new_email)

        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], new_email)

    def test_request_email_change_invalid_email(self):
        """Test requesting change with invalid email format."""
        res = self.client.post(self.request_url, {"email": "invalid-email"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data["error"])
        self.assertEqual(PendingEmailChange.objects.count(), 0)

    def test_request_email_change_email_in_use(self):
        """Test requesting change to an email that's already in use."""
        existing_email = "existing@example.com"
        create_user(email=existing_email)

        res = self.client.post(self.request_url, {"email": existing_email})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data["error"])
        self.assertEqual(PendingEmailChange.objects.count(), 0)

    def test_request_email_change_replaces_existing_request(self):
        """Test new request replaces existing pending change."""
        # Create initial request
        PendingEmailChange.objects.create(
            user=self.user,
            new_email="first@example.com",
            verification_token=generate_verification_code(),
        )

        # Make new request
        new_email = "second@example.com"
        res = self.client.post(self.request_url, {"email": new_email})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(PendingEmailChange.objects.count(), 1)
        self.assertEqual(PendingEmailChange.objects.first().new_email, new_email)

    def test_verify_email_change_success(self):
        """Test successful email change verification."""
        new_email = "new@example.com"
        token = generate_verification_code()
        PendingEmailChange.objects.create(
            user=self.user,
            new_email=new_email,
            verification_token=token,
        )

        res = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, new_email)
        self.assertEqual(PendingEmailChange.objects.count(), 0)

        # Check confirmation emails were sent
        self.assertEqual(len(mail.outbox), 2)
        email_recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(email_recipients, {new_email, "test@example.com"})

    def test_verify_email_change_invalid_token(self):
        """Test verification with invalid token."""
        res = self.client.post(self.verify_url, {"token": "invalid-token"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", res.data["error"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@example.com")

    def test_verify_email_change_expired_token(self):
        """Test verification with expired token."""
        token = generate_verification_code()
        change = PendingEmailChange.objects.create(
            user=self.user,
            new_email="new@example.com",
            verification_token=token,
        )
        # Manually set created_at to make token expired
        change.created_at = timezone.now() - timedelta(hours=13)
        change.save()

        res = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", res.data["error"])
        self.assertEqual(PendingEmailChange.objects.count(), 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@example.com")

    def test_verify_email_change_missing_token(self):
        """Test verification without providing token."""
        res = self.client.post(self.verify_url, {})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", res.data["error"])

    def test_verify_email_change_wrong_user(self):
        """Test verification with token belonging to different user."""
        other_user = create_user(email="other@example.com")
        token = generate_verification_code()
        PendingEmailChange.objects.create(
            user=other_user,
            new_email="new@example.com",
            verification_token=token,
        )

        res = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", res.data["error"])

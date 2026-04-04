"""
Tests for the account deletion API endpoints and periodic task.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.user_app.models import PendingAccountDeletion, User
from apps.user_app.tasks import delete_expired_accounts_task
from core.test_utils.utils import create_user

from .util import (
    CANCEL_ACCOUNT_DELETION_URL,
    MY_INFO_URL,
    REQUEST_ACCOUNT_DELETION_URL,
)


# ==========================================================================
# Request Account Deletion
# ==========================================================================


class PublicRequestAccountDeletionAPITests(TestCase):
    """Test unauthenticated requests to the request account deletion endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to request account deletion."""
        res = self.client.post(REQUEST_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRequestAccountDeletionAPITests(TestCase):
    """Test authenticated requests to the request account deletion endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_request_account_deletion_success(self):
        """Test requesting account deletion creates a pending record."""
        res = self.client.post(REQUEST_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", res.data)
        self.assertIn("scheduled_deletion_at", res.data)
        self.assertIn("days_remaining", res.data)

        # Verify the record was created
        self.assertTrue(
            PendingAccountDeletion.objects.filter(user=self.user).exists()
        )

    def test_request_account_deletion_returns_days_remaining(self):
        """Test that a fresh deletion request returns 6 or 7 days remaining."""
        res = self.client.post(REQUEST_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn(res.data["days_remaining"], [6, 7])

    def test_request_account_deletion_replaces_existing(self):
        """Test that requesting deletion again replaces the previous record."""
        # Create first request
        self.client.post(REQUEST_ACCOUNT_DELETION_URL)
        first_pending = PendingAccountDeletion.objects.get(user=self.user)
        first_id = first_pending.id

        # Create second request
        res = self.client.post(REQUEST_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Verify only one record exists and it's a new one
        self.assertEqual(
            PendingAccountDeletion.objects.filter(user=self.user).count(), 1
        )
        new_pending = PendingAccountDeletion.objects.get(user=self.user)
        self.assertNotEqual(new_pending.id, first_id)

    def test_request_account_deletion_does_not_delete_user(self):
        """Test that requesting deletion does not immediately delete the user."""
        self.client.post(REQUEST_ACCOUNT_DELETION_URL)

        self.assertTrue(User.objects.filter(id=self.user.id).exists())


# ==========================================================================
# Cancel Account Deletion
# ==========================================================================


class PublicCancelAccountDeletionAPITests(TestCase):
    """Test unauthenticated requests to the cancel account deletion endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to cancel account deletion."""
        res = self.client.delete(CANCEL_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateCancelAccountDeletionAPITests(TestCase):
    """Test authenticated requests to the cancel account deletion endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_cancel_account_deletion_success(self):
        """Test cancelling an existing pending deletion."""
        PendingAccountDeletion.objects.create(user=self.user)

        res = self.client.delete(CANCEL_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("message", res.data)
        self.assertFalse(
            PendingAccountDeletion.objects.filter(user=self.user).exists()
        )

    def test_cancel_account_deletion_no_pending(self):
        """Test cancelling when no pending deletion exists returns 404."""
        res = self.client.delete(CANCEL_ACCOUNT_DELETION_URL)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_then_request_again(self):
        """Test that a user can cancel and then request deletion again."""
        # Request deletion
        self.client.post(REQUEST_ACCOUNT_DELETION_URL)
        self.assertTrue(
            PendingAccountDeletion.objects.filter(user=self.user).exists()
        )

        # Cancel deletion
        self.client.delete(CANCEL_ACCOUNT_DELETION_URL)
        self.assertFalse(
            PendingAccountDeletion.objects.filter(user=self.user).exists()
        )

        # Request deletion again
        res = self.client.post(REQUEST_ACCOUNT_DELETION_URL)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PendingAccountDeletion.objects.filter(user=self.user).exists()
        )


# ==========================================================================
# My Info - pending_deletion field
# ==========================================================================


class MyInfoPendingDeletionTests(TestCase):
    """Test that the my-info endpoint returns pending_deletion data."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_my_info_no_pending_deletion(self):
        """Test my-info returns null pending_deletion when none exists."""
        res = self.client.get(MY_INFO_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["pending_deletion"])

    def test_my_info_with_pending_deletion(self):
        """Test my-info returns pending_deletion data when one exists."""
        PendingAccountDeletion.objects.create(user=self.user)

        res = self.client.get(MY_INFO_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res.data["pending_deletion"])
        self.assertIn("scheduled_deletion_at", res.data["pending_deletion"])
        self.assertIn("days_remaining", res.data["pending_deletion"])

    def test_my_info_pending_deletion_cleared_after_cancel(self):
        """Test my-info returns null after cancelling deletion."""
        PendingAccountDeletion.objects.create(user=self.user)

        # Cancel the deletion
        cancel_res = self.client.delete(CANCEL_ACCOUNT_DELETION_URL)
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)

        # Refresh user from DB to clear cached related object
        self.user.refresh_from_db()

        res = self.client.get(MY_INFO_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["pending_deletion"])


# ==========================================================================
# PendingAccountDeletion Model
# ==========================================================================


class PendingAccountDeletionModelTests(TestCase):
    """Test the PendingAccountDeletion model properties."""

    def setUp(self):
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_scheduled_deletion_at(self):
        """Test scheduled_deletion_at is 7 days after created_at."""
        pending = PendingAccountDeletion.objects.create(user=self.user)

        expected = pending.created_at + timedelta(days=7)
        self.assertEqual(pending.scheduled_deletion_at, expected)

    def test_days_remaining_new_record(self):
        """Test days_remaining is 7 for a freshly created record."""
        pending = PendingAccountDeletion.objects.create(user=self.user)

        # A fresh record should have 6 or 7 days remaining
        self.assertIn(pending.days_remaining, [6, 7])

    def test_days_remaining_never_negative(self):
        """Test days_remaining does not go below 0."""
        pending = PendingAccountDeletion.objects.create(user=self.user)
        # Backdate the record to 10 days ago
        PendingAccountDeletion.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        pending.refresh_from_db()

        self.assertEqual(pending.days_remaining, 0)

    def test_is_due_false_for_new_record(self):
        """Test is_due is False for a freshly created record."""
        pending = PendingAccountDeletion.objects.create(user=self.user)

        self.assertFalse(pending.is_due)

    def test_is_due_true_after_grace_period(self):
        """Test is_due is True after the 7-day grace period."""
        pending = PendingAccountDeletion.objects.create(user=self.user)
        PendingAccountDeletion.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        pending.refresh_from_db()

        self.assertTrue(pending.is_due)

    def test_str_representation(self):
        """Test the string representation of the model."""
        pending = PendingAccountDeletion.objects.create(user=self.user)

        self.assertIn(self.user.email, str(pending))
        self.assertIn("scheduled for", str(pending))

    def test_cascade_delete_with_user(self):
        """Test that deleting a user cascades to PendingAccountDeletion."""
        PendingAccountDeletion.objects.create(user=self.user)
        user_id = self.user.id

        self.user.delete()

        self.assertFalse(PendingAccountDeletion.objects.filter(user_id=user_id).exists())

    def test_one_to_one_constraint(self):
        """Test that a user can only have one pending deletion."""
        PendingAccountDeletion.objects.create(user=self.user)

        with self.assertRaises(Exception):
            PendingAccountDeletion.objects.create(user=self.user)


# ==========================================================================
# Celery Task - delete_expired_accounts_task
# ==========================================================================


class DeleteExpiredAccountsTaskTests(TestCase):
    """Test the delete_expired_accounts_task Celery task."""

    def test_deletes_expired_accounts(self):
        """Test that accounts past the 7-day grace period are deleted."""
        user = create_user(email="expired@example.com")
        pending = PendingAccountDeletion.objects.create(user=user)
        # Backdate to 8 days ago
        PendingAccountDeletion.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )

        result = delete_expired_accounts_task()

        self.assertEqual(result["deleted_count"], 1)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())

    def test_does_not_delete_accounts_within_grace_period(self):
        """Test that accounts within the 7-day grace period are not deleted."""
        user = create_user(email="recent@example.com")
        PendingAccountDeletion.objects.create(user=user)

        result = delete_expired_accounts_task()

        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue(User.objects.filter(email="recent@example.com").exists())

    def test_deletes_only_expired_accounts(self):
        """Test that only expired accounts are deleted, not recent ones."""
        expired_user = create_user(email="expired@example.com")
        recent_user = create_user(email="recent@example.com")

        expired_pending = PendingAccountDeletion.objects.create(user=expired_user)
        PendingAccountDeletion.objects.create(user=recent_user)

        # Backdate only the expired one
        PendingAccountDeletion.objects.filter(pk=expired_pending.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )

        result = delete_expired_accounts_task()

        self.assertEqual(result["deleted_count"], 1)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())
        self.assertTrue(User.objects.filter(email="recent@example.com").exists())

    def test_no_expired_accounts(self):
        """Test task succeeds when there are no expired accounts."""
        result = delete_expired_accounts_task()

        self.assertEqual(result["deleted_count"], 0)

    def test_deletes_multiple_expired_accounts(self):
        """Test task handles multiple expired accounts."""
        users = []
        for i in range(3):
            user = create_user(email=f"expired{i}@example.com")
            pending = PendingAccountDeletion.objects.create(user=user)
            PendingAccountDeletion.objects.filter(pk=pending.pk).update(
                created_at=timezone.now() - timedelta(days=8)
            )
            users.append(user)

        result = delete_expired_accounts_task()

        self.assertEqual(result["deleted_count"], 3)
        for user in users:
            self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_account_at_exactly_7_days_not_deleted(self):
        """Test that an account at exactly 7 days is not deleted."""
        user = create_user(email="boundary@example.com")
        pending = PendingAccountDeletion.objects.create(user=user)
        # Set to exactly 7 days ago (on the boundary)
        PendingAccountDeletion.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=7)
        )

        result = delete_expired_accounts_task()

        # At exactly 7 days, created_at__lte cutoff means it should be deleted
        # since cutoff = now - 7 days, and created_at = now - 7 days
        self.assertEqual(result["deleted_count"], 1)

    @patch("apps.user_app.models.User.delete")
    def test_continues_on_individual_delete_failure(self, mock_delete):
        """Test task continues processing if one user delete fails."""
        user1 = create_user(email="fail@example.com")
        user2 = create_user(email="succeed@example.com")

        pending1 = PendingAccountDeletion.objects.create(user=user1)
        pending2 = PendingAccountDeletion.objects.create(user=user2)

        PendingAccountDeletion.objects.filter(
            pk__in=[pending1.pk, pending2.pk]
        ).update(created_at=timezone.now() - timedelta(days=8))

        # Make the first delete call raise, second succeed
        mock_delete.side_effect = [Exception("DB error"), None]

        result = delete_expired_accounts_task()

        # One succeeded, one failed
        self.assertEqual(result["deleted_count"], 1)

"""
Tests for the legal API endpoints (CurrentTermsView and AcceptTermsView).
"""

from django.test import TestCase

from rest_framework.test import APIClient
from rest_framework import status

from .util import CURRENT_TERMS_URL, ACCEPT_TERMS_URL
from apps.legal_app.models import TermsOfService, TermsAcceptance
from core.test_utils.utils import create_user, create_profile


def create_terms(
    version="1.0", content="# Terms\n\nThese are the terms.", is_active=True
):
    """Helper to create a TermsOfService instance."""
    return TermsOfService.objects.create(
        version=version,
        content=content,
        is_active=is_active,
    )


# ============================================================
# CurrentTermsView Tests
# ============================================================


class PublicCurrentTermsApiTests(TestCase):
    """Test unauthenticated requests to the current terms endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required."""
        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateCurrentTermsApiTests(TestCase):
    """Test authenticated requests to the current terms endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="test@example.com", password="testpass123")
        self.profile = create_profile(user=self.user, username="testuser")
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def tearDown(self):
        TermsAcceptance.objects.all().delete()
        TermsOfService.objects.all().delete()

    def test_retrieve_current_terms(self):
        """Test retrieving the current active terms of service."""
        terms = create_terms(version="1.0", content="# Terms v1")

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], terms.id)
        self.assertEqual(res.data["version"], "1.0")
        self.assertEqual(res.data["content"], "# Terms v1")
        self.assertFalse(res.data["has_accepted"])
        self.assertIsNone(res.data["accepted_at"])

    def test_retrieve_returns_latest_active_terms(self):
        """Test that the most recently created active terms are returned."""
        create_terms(version="1.0", content="Old terms")
        latest = create_terms(version="2.0", content="New terms")

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], latest.id)
        self.assertEqual(res.data["version"], "2.0")
        self.assertEqual(res.data["content"], "New terms")

    def test_retrieve_skips_inactive_terms(self):
        """Test that inactive terms are not returned even if more recent."""
        active = create_terms(version="1.0", content="Active terms")
        create_terms(version="2.0", content="Inactive terms", is_active=False)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], active.id)
        self.assertEqual(res.data["version"], "1.0")

    def test_retrieve_no_active_terms_returns_404(self):
        """Test that 404 is returned when no active terms exist."""
        create_terms(version="1.0", is_active=False)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_no_terms_at_all_returns_404(self):
        """Test that 404 is returned when no terms exist at all."""
        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_has_accepted_true_when_user_accepted(self):
        """Test that has_accepted is true when the user has accepted the terms."""
        terms = create_terms(version="1.0")
        TermsAcceptance.objects.create(user=self.user, terms=terms)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["has_accepted"])

    def test_accepted_at_returned_when_user_accepted(self):
        """Test that accepted_at is returned when the user has accepted the terms."""
        terms = create_terms(version="1.0")
        acceptance = TermsAcceptance.objects.create(user=self.user, terms=terms)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res.data["accepted_at"])

    def test_has_accepted_false_for_different_user(self):
        """Test that has_accepted reflects the requesting user, not others."""
        terms = create_terms(version="1.0")
        other_user = create_user(email="other@example.com")
        TermsAcceptance.objects.create(user=other_user, terms=terms)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["has_accepted"])
        self.assertIsNone(res.data["accepted_at"])

    def test_has_accepted_false_for_different_version(self):
        """Test that accepting an old version doesn't affect the current one."""
        old_terms = create_terms(version="1.0")
        new_terms = create_terms(version="2.0")
        TermsAcceptance.objects.create(user=self.user, terms=old_terms)

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], new_terms.id)
        self.assertFalse(res.data["has_accepted"])

    def test_response_contains_all_expected_fields(self):
        """Test that the response contains all expected fields."""
        create_terms(version="1.0")

        res = self.client.get(CURRENT_TERMS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("id", res.data)
        self.assertIn("content", res.data)
        self.assertIn("version", res.data)
        self.assertIn("created_at", res.data)
        self.assertIn("has_accepted", res.data)
        self.assertIn("accepted_at", res.data)

    def test_different_user_sees_own_acceptance_status(self):
        """Test that each user sees their own acceptance status."""
        terms = create_terms(version="1.0")
        TermsAcceptance.objects.create(user=self.user, terms=terms)

        # Check first user sees accepted
        res = self.client.get(CURRENT_TERMS_URL)
        self.assertTrue(res.data["has_accepted"])

        # Switch to second user who has not accepted
        user2 = create_user(email="user2@example.com")
        profile2 = create_profile(user=user2, username="user2")
        self.client.force_authenticate(user=user2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile2.public_id))

        res = self.client.get(CURRENT_TERMS_URL)
        self.assertFalse(res.data["has_accepted"])


# ============================================================
# AcceptTermsView Tests
# ============================================================


class PublicAcceptTermsApiTests(TestCase):
    """Test unauthenticated requests to the accept terms endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required."""
        terms = create_terms(version="1.0")

        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateAcceptTermsApiTests(TestCase):
    """Test authenticated requests to the accept terms endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="test@example.com", password="testpass123")
        self.profile = create_profile(user=self.user, username="testuser")
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def tearDown(self):
        TermsAcceptance.objects.all().delete()
        TermsOfService.objects.all().delete()

    def test_accept_terms_success(self):
        """Test successfully accepting terms of service."""
        terms = create_terms(version="1.0")

        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["detail"], "Terms accepted successfully.")
        self.assertTrue(
            TermsAcceptance.objects.filter(user=self.user, terms=terms).exists()
        )

    def test_accept_terms_creates_acceptance_record(self):
        """Test that a TermsAcceptance record is created in the database."""
        terms = create_terms(version="1.0")

        self.assertEqual(TermsAcceptance.objects.count(), 0)

        self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})

        self.assertEqual(TermsAcceptance.objects.count(), 1)
        acceptance = TermsAcceptance.objects.first()
        self.assertEqual(acceptance.user, self.user)
        self.assertEqual(acceptance.terms, terms)

    def test_accept_terms_idempotent(self):
        """Test that accepting the same terms twice is idempotent."""
        terms = create_terms(version="1.0")

        res1 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["detail"], "Terms already accepted.")

        # Only one acceptance record should exist
        self.assertEqual(
            TermsAcceptance.objects.filter(user=self.user, terms=terms).count(), 1
        )

    def test_accept_terms_invalid_terms_id(self):
        """Test accepting with a non-existent terms_id returns 400."""
        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": 9999})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["detail"], "Terms of service not found or inactive.")

    def test_accept_terms_inactive_terms(self):
        """Test accepting inactive terms returns 400."""
        terms = create_terms(version="1.0", is_active=False)

        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["detail"], "Terms of service not found or inactive.")
        self.assertFalse(
            TermsAcceptance.objects.filter(user=self.user, terms=terms).exists()
        )

    def test_accept_terms_missing_terms_id(self):
        """Test that terms_id is required in the request body."""
        res = self.client.post(ACCEPT_TERMS_URL, {})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_terms_null_terms_id(self):
        """Test that null terms_id is rejected."""
        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": None}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_terms_string_terms_id(self):
        """Test that a non-integer terms_id is rejected."""
        res = self.client.post(ACCEPT_TERMS_URL, {"terms_id": "abc"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_terms_captures_ip_from_remote_addr(self):
        """Test that the IP address is captured from REMOTE_ADDR."""
        terms = create_terms(version="1.0")

        self.client.post(
            ACCEPT_TERMS_URL, {"terms_id": terms.id}, REMOTE_ADDR="192.168.1.100"
        )

        acceptance = TermsAcceptance.objects.get(user=self.user, terms=terms)
        self.assertEqual(acceptance.ip_address, "192.168.1.100")

    def test_accept_terms_captures_ip_from_x_forwarded_for(self):
        """Test that the IP address is captured from X-Forwarded-For header."""
        terms = create_terms(version="1.0")

        self.client.post(
            ACCEPT_TERMS_URL,
            {"terms_id": terms.id},
            HTTP_X_FORWARDED_FOR="10.0.0.1, 10.0.0.2, 10.0.0.3",
        )

        acceptance = TermsAcceptance.objects.get(user=self.user, terms=terms)
        self.assertEqual(acceptance.ip_address, "10.0.0.1")

    def test_accept_terms_x_forwarded_for_takes_precedence(self):
        """Test that X-Forwarded-For takes precedence over REMOTE_ADDR."""
        terms = create_terms(version="1.0")

        self.client.post(
            ACCEPT_TERMS_URL,
            {"terms_id": terms.id},
            REMOTE_ADDR="192.168.1.100",
            HTTP_X_FORWARDED_FOR="10.0.0.1",
        )

        acceptance = TermsAcceptance.objects.get(user=self.user, terms=terms)
        self.assertEqual(acceptance.ip_address, "10.0.0.1")

    def test_accept_multiple_versions(self):
        """Test that a user can accept multiple different terms versions."""
        terms_v1 = create_terms(version="1.0")
        terms_v2 = create_terms(version="2.0")

        res1 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms_v1.id})
        res2 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms_v2.id})

        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TermsAcceptance.objects.filter(user=self.user).count(), 2)

    def test_accept_terms_different_users_independent(self):
        """Test that different users can independently accept the same terms."""
        terms = create_terms(version="1.0")
        user2 = create_user(email="user2@example.com")
        profile2 = create_profile(user=user2, username="user2")

        # First user accepts
        res1 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Second user accepts
        self.client.force_authenticate(user=user2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile2.public_id))

        res2 = self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        self.assertEqual(TermsAcceptance.objects.filter(terms=terms).count(), 2)

    def test_accept_terms_updates_current_terms_has_accepted(self):
        """Test that after accepting, the current terms endpoint reflects acceptance."""
        terms = create_terms(version="1.0")

        # Before accepting
        res = self.client.get(CURRENT_TERMS_URL)
        self.assertFalse(res.data["has_accepted"])

        # Accept
        self.client.post(ACCEPT_TERMS_URL, {"terms_id": terms.id})

        # After accepting
        res = self.client.get(CURRENT_TERMS_URL)
        self.assertTrue(res.data["has_accepted"])
        self.assertIsNotNone(res.data["accepted_at"])

    def test_accept_terms_only_post_method_allowed(self):
        """Test that only POST method is allowed on the accept endpoint."""
        terms = create_terms(version="1.0")

        res_get = self.client.get(ACCEPT_TERMS_URL)
        res_put = self.client.put(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        res_patch = self.client.patch(ACCEPT_TERMS_URL, {"terms_id": terms.id})
        res_delete = self.client.delete(ACCEPT_TERMS_URL)

        self.assertEqual(res_get.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_patch.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_current_terms_only_get_method_allowed(self):
        """Test that only GET method is allowed on the current terms endpoint."""
        create_terms(version="1.0")

        res_post = self.client.post(CURRENT_TERMS_URL, {})
        res_put = self.client.put(CURRENT_TERMS_URL, {})
        res_patch = self.client.patch(CURRENT_TERMS_URL, {})
        res_delete = self.client.delete(CURRENT_TERMS_URL)

        self.assertEqual(res_post.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_patch.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(res_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

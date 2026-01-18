"""
Tests for the admin report reason detail API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile, create_report_reason


def get_admin_report_reason_detail_url(reason_id):
    """Return admin report reason detail URL."""
    return reverse("admin-report-reason-detail", kwargs={"pk": reason_id})


class PublicAdminReportReasonDetailTests(TestCase):
    """Tests for unauthenticated access to admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.reason = create_report_reason("Test Reason", "Test description")

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_put_returns_401(self):
        """Test that unauthenticated PUT requests return 401."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.put(url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_delete_returns_401(self):
        """Test that unauthenticated DELETE requests return 401."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminReportReasonDetailTests(TestCase):
    """Tests for non-admin authenticated access to admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.reason = create_report_reason("Test Reason", "Test description")
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=profile.id)

        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminReportReasonDetailGetTests(TestCase):
    """Tests for GET requests to admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.reason = create_report_reason("Inappropriate Content", "Content is inappropriate or offensive")

    def test_admin_can_retrieve_report_reason(self):
        """Test that admin users can retrieve report reason details."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertIn("name", response.data)
        self.assertIn("description", response.data)
        self.assertIn("is_active", response.data)
        self.assertIn("created_at", response.data)

    def test_returns_correct_report_reason_data(self):
        """Test that the correct report reason data is returned."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.reason.id)
        self.assertEqual(response.data["name"], "Inappropriate Content")
        self.assertEqual(response.data["description"], "Content is inappropriate or offensive")
        self.assertTrue(response.data["is_active"])

    def test_nonexistent_report_reason_returns_404(self):
        """Test that requesting a nonexistent report reason returns 404."""
        url = get_admin_report_reason_detail_url(99999)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminReportReasonDetailUpdateTests(TestCase):
    """Tests for PUT/PATCH requests to admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.reason = create_report_reason("Original Name", "Original description")

    def test_admin_can_update_report_reason_with_put(self):
        """Test that admin users can fully update report reason with PUT."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "is_active": False,
        }
        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")
        self.assertEqual(response.data["description"], "Updated description")
        self.assertFalse(response.data["is_active"])

    def test_admin_can_partial_update_with_patch(self):
        """Test that admin users can partially update report reason with PATCH."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        data = {"name": "Patched Name"}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Patched Name")
        # Original description should be unchanged
        self.assertEqual(response.data["description"], "Original description")

    def test_update_name(self):
        """Test updating report reason name."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"name": "New Name"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "New Name")

    def test_update_description(self):
        """Test updating report reason description."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"description": "New description"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "New description")

    def test_update_is_active(self):
        """Test updating report reason is_active status."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"is_active": False}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_reactivate_reason(self):
        """Test reactivating an inactive report reason."""
        self.reason.is_active = False
        self.reason.save()

        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"is_active": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    def test_cannot_update_id(self):
        """Test that id cannot be updated (read-only)."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        original_id = self.reason.id
        response = self.client.patch(url, {"id": 99999}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], original_id)

    def test_cannot_update_created_at(self):
        """Test that created_at cannot be updated (read-only)."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(
            url,
            {"created_at": "2020-01-01T00:00:00Z"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # created_at should remain unchanged

    def test_update_nonexistent_report_reason_returns_404(self):
        """Test that updating a nonexistent report reason returns 404."""
        url = get_admin_report_reason_detail_url(99999)
        response = self.client.patch(url, {"name": "New Name"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminReportReasonDetailDeleteTests(TestCase):
    """Tests for DELETE requests to admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_delete_report_reason(self):
        """Test that admin users can delete report reasons."""
        reason = create_report_reason("To Delete", "Will be deleted")
        url = get_admin_report_reason_detail_url(reason.id)

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify reason is deleted
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_report_reason_returns_404(self):
        """Test that deleting a nonexistent report reason returns 404."""
        url = get_admin_report_reason_detail_url(99999)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_from_list(self):
        """Test that deleted report reason no longer appears in list."""
        reason = create_report_reason("To Delete", "Will be deleted")
        reason_id = reason.id

        url = get_admin_report_reason_detail_url(reason_id)
        self.client.delete(url)

        list_url = reverse("admin-report-reason-list")
        response = self.client.get(list_url)

        ids = [r["id"] for r in response.data["results"]]
        self.assertNotIn(reason_id, ids)


class AdminReportReasonDetailValidationTests(TestCase):
    """Validation tests for admin report reason detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.reason = create_report_reason("Original Name", "Original description")

    def test_update_with_empty_name_fails(self):
        """Test that updating with empty name fails validation."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"name": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_with_duplicate_name_fails(self):
        """Test that updating with duplicate name fails validation."""
        create_report_reason("Existing Name", "Description")

        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"name": "Existing Name"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_description_to_empty_succeeds(self):
        """Test that updating description to empty string succeeds."""
        url = get_admin_report_reason_detail_url(self.reason.id)
        response = self.client.patch(url, {"description": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "")


class AdminReportReasonDetailEdgeCasesTests(TestCase):
    """Edge case tests for admin report reason detail."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_invalid_report_reason_id_format(self):
        """Test that invalid report reason ID format is handled."""
        url = "/api/admin/report-reasons/invalid/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_superuser_can_access(self):
        """Test that superusers can access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        reason = create_report_reason("Test Reason", "Description")

        url = get_admin_report_reason_detail_url(reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_update(self):
        """Test that superusers can update report reasons."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        reason = create_report_reason("Test Reason", "Description")

        url = get_admin_report_reason_detail_url(reason.id)
        response = self.client.patch(url, {"name": "Updated Name"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")

    def test_superuser_can_delete(self):
        """Test that superusers can delete report reasons."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        reason = create_report_reason("Test Reason", "Description")

        url = get_admin_report_reason_detail_url(reason.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_concurrent_updates(self):
        """Test that concurrent updates work correctly."""
        reason = create_report_reason("Original", "Description")
        url = get_admin_report_reason_detail_url(reason.id)

        # First update
        self.client.patch(url, {"name": "First Update"}, format="json")
        # Second update
        response = self.client.patch(url, {"description": "Second Update"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "First Update")
        self.assertEqual(response.data["description"], "Second Update")

    def test_special_characters_in_name(self):
        """Test updating reason with special characters in name."""
        reason = create_report_reason("Original", "Description")
        url = get_admin_report_reason_detail_url(reason.id)

        response = self.client.patch(
            url,
            {"name": "Test & Reason (Special)"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test & Reason (Special)")

    def test_long_description_update(self):
        """Test updating reason with long description."""
        reason = create_report_reason("Original", "Description")
        url = get_admin_report_reason_detail_url(reason.id)

        long_description = "A" * 1000
        response = self.client.patch(
            url,
            {"description": long_description},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], long_description)

    def test_inactive_reason_details(self):
        """Test retrieving details of inactive report reason."""
        reason = create_report_reason("Inactive Reason", "Description", is_active=False)

        url = get_admin_report_reason_detail_url(reason.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

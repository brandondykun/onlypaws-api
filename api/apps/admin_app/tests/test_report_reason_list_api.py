"""
Tests for the admin report reason list API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile, create_report_reason


ADMIN_REPORT_REASON_LIST_URL = reverse("admin-report-reason-list")


class PublicAdminReportReasonListTests(TestCase):
    """Tests for unauthenticated access to admin report reason list endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_REPORT_REASON_LIST_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminReportReasonListTests(TestCase):
    """Tests for non-admin authenticated access to admin report reason list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=profile.id)

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminReportReasonListTests(TestCase):
    """Tests for admin access to the report reason list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_report_reason_list(self):
        """Test that admin users can access the report reason list endpoint."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_pagination_fields(self):
        """Test that response contains pagination fields."""
        create_report_reason("Test Reason", "Test description")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_response_contains_required_report_reason_fields(self):
        """Test that report reason objects contain all required fields."""
        create_report_reason("Test Reason", "Test description")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        reason_data = response.data["results"][0]
        self.assertIn("id", reason_data)
        self.assertIn("name", reason_data)
        self.assertIn("description", reason_data)
        self.assertIn("is_active", reason_data)
        self.assertIn("created_at", reason_data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_REPORT_REASON_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_REPORT_REASON_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_REPORT_REASON_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_REPORT_REASON_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lists_all_report_reasons(self):
        """Test that endpoint lists all report reasons."""
        create_report_reason("Inappropriate Content", "Content is inappropriate")
        create_report_reason("Spam", "Content is spam")
        create_report_reason("Harassment", "Content is harassment")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_empty_report_reason_list(self):
        """Test response when no report reasons exist."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_includes_inactive_report_reasons(self):
        """Test that inactive report reasons are included in the list."""
        create_report_reason("Active Reason", "Description", is_active=True)
        create_report_reason("Inactive Reason", "Description", is_active=False)

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class AdminReportReasonListSearchTests(TestCase):
    """Tests for search functionality in admin report reason list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        self.reason1 = create_report_reason("Inappropriate Content", "Content is inappropriate")
        self.reason2 = create_report_reason("Spam Content", "Content is spam")
        self.reason3 = create_report_reason("Harassment", "User harassment")

    def test_search_by_name_partial_match(self):
        """Test searching report reasons by partial name match."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"search": "Content"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        names = [r["name"] for r in response.data["results"]]
        self.assertIn("Inappropriate Content", names)
        self.assertIn("Spam Content", names)

    def test_search_by_name_exact_match(self):
        """Test searching report reasons by exact name."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"search": "Harassment"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Harassment")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"search": "CONTENT"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_search_no_results(self):
        """Test search with no matching results."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"search": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_empty_string_returns_all(self):
        """Test that empty search string returns all report reasons."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"search": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)


class AdminReportReasonListOrderingTests(TestCase):
    """Tests for ordering functionality in admin report reason list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        self.reason_z = create_report_reason("Zebra Reason", "Description")
        self.reason_a = create_report_reason("Alpha Reason", "Description")
        self.reason_m = create_report_reason("Middle Reason", "Description")

    def test_default_ordering_by_name(self):
        """Test that default ordering is by name."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_ordering_by_id_ascending(self):
        """Test ordering report reasons by id ascending."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"ordering": "id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(ids, sorted(ids))

    def test_ordering_by_id_descending(self):
        """Test ordering report reasons by id descending."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"ordering": "-id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data["results"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_ordering_by_name_ascending(self):
        """Test ordering report reasons by name ascending."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"ordering": "name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_ordering_by_name_descending(self):
        """Test ordering report reasons by name descending."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"ordering": "-name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_ordering_by_is_active(self):
        """Test ordering report reasons by is_active status."""
        self.reason_a.is_active = False
        self.reason_a.save()

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"ordering": "is_active"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inactive reason (False) should come first
        self.assertFalse(response.data["results"][0]["is_active"])


class AdminReportReasonListPaginationTests(TestCase):
    """Tests for pagination in admin report reason list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_default_page_size(self):
        """Test that default page size is 25."""
        for i in range(30):
            create_report_reason(f"Reason {i:02d}", f"Description {i}")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_custom_page_size(self):
        """Test custom page_size parameter."""
        for i in range(15):
            create_report_reason(f"Reason {i}", f"Description {i}")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)

    def test_page_size_max_limit(self):
        """Test that page_size respects max limit of 100."""
        for i in range(105):
            create_report_reason(f"Reason {i:03d}", f"Description {i}")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"page_size": 200})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data["results"]), 100)

    def test_pagination_second_page(self):
        """Test accessing the second page of results."""
        for i in range(30):
            create_report_reason(f"Reason {i:02d}", f"Description {i}")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_page_returns_404(self):
        """Test that requesting an invalid page returns 404."""
        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL, {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminReportReasonListEdgeCasesTests(TestCase):
    """Edge case tests for admin report reason list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_reason_with_empty_description(self):
        """Test that reasons with empty description are listed."""
        create_report_reason("No Description", "")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["description"], "")

    def test_reason_with_long_description(self):
        """Test that reasons with long descriptions are listed."""
        long_description = "A" * 1000
        create_report_reason("Long Description", long_description)

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["description"], long_description)

    def test_superuser_can_access(self):
        """Test that superusers can also access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        create_report_reason("Test Reason", "Description")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_special_characters_in_name(self):
        """Test that reasons with special characters in name are listed."""
        create_report_reason("Test & Reason (Special)", "Description with <special> chars")

        response = self.client.get(ADMIN_REPORT_REASON_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Test & Reason (Special)")

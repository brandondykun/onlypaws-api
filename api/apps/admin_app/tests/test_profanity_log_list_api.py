"""
Tests for the admin profanity log list API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile, create_profanity_log


ADMIN_PROFANITY_LOG_LIST_URL = reverse("admin-profanity-log-list")


class PublicAdminProfanityLogListTests(TestCase):
    """Tests for unauthenticated access to admin profanity log list endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_PROFANITY_LOG_LIST_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminProfanityLogListTests(TestCase):
    """Tests for non-admin authenticated access to admin profanity log list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminProfanityLogListTests(TestCase):
    """Tests for admin access to the profanity log list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_profanity_log_list(self):
        """Test that admin users can access the profanity log list endpoint."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_pagination_fields(self):
        """Test that response contains pagination fields."""
        create_profanity_log("bad word")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_response_contains_required_fields(self):
        """Test that profanity log objects contain all required fields."""
        create_profanity_log("bad word")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        log_data = response.data["results"][0]
        self.assertIn("id", log_data)
        self.assertIn("original_text", log_data)
        self.assertIn("content_type", log_data)
        self.assertIn("detection_method", log_data)
        self.assertIn("detection_details", log_data)
        self.assertIn("profile", log_data)
        self.assertIn("profile_username", log_data)
        self.assertIn("created_at", log_data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_PROFANITY_LOG_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_PROFANITY_LOG_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_PROFANITY_LOG_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_PROFANITY_LOG_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lists_all_profanity_logs(self):
        """Test that endpoint lists all profanity logs."""
        create_profanity_log("bad word 1")
        create_profanity_log("bad word 2")
        create_profanity_log("bad word 3")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_empty_profanity_log_list(self):
        """Test response when no profanity logs exist."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_log_with_profile_shows_username(self):
        """Test that log linked to a profile shows the profile username."""
        user = create_user("loguser@example.com", "password123")
        profile = create_profile("log_profile", user)
        create_profanity_log("bad word", profile=profile)

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log_data = response.data["results"][0]
        self.assertEqual(log_data["profile_username"], "log_profile")

    def test_log_without_profile_shows_null(self):
        """Test that log without a profile shows null profile and profile_username."""
        create_profanity_log("bad word", profile=None)

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log_data = response.data["results"][0]
        self.assertIsNone(log_data["profile"])
        self.assertIsNone(log_data["profile_username"])


class AdminProfanityLogListFilterTests(TestCase):
    """Tests for filtering functionality in admin profanity log list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

        self.log1 = create_profanity_log("bad comment", content_type="COMMENT", detection_method="WORD_MATCH")
        self.log2 = create_profanity_log("bad username", content_type="USERNAME", detection_method="ML")
        self.log3 = create_profanity_log("bad caption", content_type="COMMENT", detection_method="ML")

    def test_filter_by_content_type(self):
        """Test filtering profanity logs by content_type."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"content_type": "COMMENT"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        for log in response.data["results"]:
            self.assertEqual(log["content_type"], "COMMENT")

    def test_filter_by_detection_method(self):
        """Test filtering profanity logs by detection_method."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"detection_method": "ML"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        for log in response.data["results"]:
            self.assertEqual(log["detection_method"], "ML")

    def test_filter_by_both_content_type_and_detection_method(self):
        """Test filtering by both content_type and detection_method."""
        response = self.client.get(
            ADMIN_PROFANITY_LOG_LIST_URL,
            {"content_type": "COMMENT", "detection_method": "ML"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["content_type"], "COMMENT")
        self.assertEqual(response.data["results"][0]["detection_method"], "ML")

    def test_no_filter_returns_all(self):
        """Test that no query params returns all logs."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)


class AdminProfanityLogListSearchTests(TestCase):
    """Tests for search functionality in admin profanity log list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

        self.user = create_user("searchuser@example.com", "password123")
        self.profile = create_profile("search_profile", self.user)

        self.log1 = create_profanity_log("offensive comment here", profile=self.profile)
        self.log2 = create_profanity_log("another bad word")
        self.log3 = create_profanity_log("clean looking text")

    def test_search_by_original_text(self):
        """Test searching profanity logs by original_text."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"search": "offensive"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("offensive", response.data["results"][0]["original_text"])

    def test_search_by_profile_username(self):
        """Test searching profanity logs by profile username."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"search": "search_profile"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["profile_username"], "search_profile")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"search": "OFFENSIVE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_no_results(self):
        """Test search with no matching results."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"search": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)


class AdminProfanityLogListOrderingTests(TestCase):
    """Tests for ordering functionality in admin profanity log list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

        self.log1 = create_profanity_log("first log")
        self.log2 = create_profanity_log("second log")
        self.log3 = create_profanity_log("third log")

    def test_default_ordering_by_created_at_desc(self):
        """Test that default ordering is by -created_at (newest first)."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        # Newest first
        self.assertEqual(results[0]["id"], self.log3.id)
        self.assertEqual(results[-1]["id"], self.log1.id)

    def test_ordering_by_id_ascending(self):
        """Test ordering profanity logs by id ascending."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"ordering": "id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [log["id"] for log in response.data["results"]]
        self.assertEqual(ids, sorted(ids))

    def test_ordering_by_id_descending(self):
        """Test ordering profanity logs by id descending."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"ordering": "-id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [log["id"] for log in response.data["results"]]
        self.assertEqual(ids, sorted(ids, reverse=True))


class AdminProfanityLogListPaginationTests(TestCase):
    """Tests for pagination in admin profanity log list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_default_page_size(self):
        """Test that default page size is 25."""
        for i in range(30):
            create_profanity_log(f"bad word {i}")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_custom_page_size(self):
        """Test custom page_size parameter."""
        for i in range(15):
            create_profanity_log(f"bad word {i}")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)

    def test_pagination_second_page(self):
        """Test accessing the second page of results."""
        for i in range(30):
            create_profanity_log(f"bad word {i}")

        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_page_returns_404(self):
        """Test that requesting an invalid page returns 404."""
        response = self.client.get(ADMIN_PROFANITY_LOG_LIST_URL, {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

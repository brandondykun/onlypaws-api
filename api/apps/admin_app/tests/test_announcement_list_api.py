"""
Tests for the admin announcement list API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta

from core.test_utils.utils import create_user, create_profile, create_announcement


ADMIN_ANNOUNCEMENT_LIST_URL = reverse("admin-announcement-list")


class PublicAdminAnnouncementListTests(TestCase):
    """Tests for unauthenticated access to admin announcement list endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_ANNOUNCEMENT_LIST_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminAnnouncementListTests(TestCase):
    """Tests for non-admin authenticated access to admin announcement list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminAnnouncementListTests(TestCase):
    """Tests for admin access to the announcement list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_announcement_list(self):
        """Test that admin users can access the announcement list endpoint."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_pagination_fields(self):
        """Test that response contains pagination fields."""
        create_announcement("Test Announcement", "Test message")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_response_contains_required_announcement_fields(self):
        """Test that announcement objects contain all required fields."""
        create_announcement("Test Announcement", "Test message")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        announcement_data = response.data["results"][0]
        self.assertIn("id", announcement_data)
        self.assertIn("title", announcement_data)
        self.assertIn("priority", announcement_data)
        self.assertIn("announcement_type", announcement_data)
        self.assertIn("is_active", announcement_data)
        self.assertIn("start_date", announcement_data)
        self.assertIn("end_date", announcement_data)
        self.assertIn("created_at", announcement_data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_ANNOUNCEMENT_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_ANNOUNCEMENT_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_ANNOUNCEMENT_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_ANNOUNCEMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lists_all_announcements(self):
        """Test that endpoint lists all announcements."""
        create_announcement("Announcement 1", "Message 1")
        create_announcement("Announcement 2", "Message 2")
        create_announcement("Announcement 3", "Message 3")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_empty_announcement_list(self):
        """Test response when no announcements exist."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_includes_inactive_announcements(self):
        """Test that inactive announcements are included in the list."""
        create_announcement("Active Announcement", "Message", is_active=True)
        create_announcement("Inactive Announcement", "Message", is_active=False)

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class AdminAnnouncementListSearchTests(TestCase):
    """Tests for search functionality in admin announcement list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        self.announcement1 = create_announcement("System Maintenance", "We will be performing maintenance")
        self.announcement2 = create_announcement("New Feature Release", "Exciting new features")
        self.announcement3 = create_announcement("System Update", "Important system update")

    def test_search_by_title_partial_match(self):
        """Test searching announcements by partial title match."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"search": "System"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        titles = [a["title"] for a in response.data["results"]]
        self.assertIn("System Maintenance", titles)
        self.assertIn("System Update", titles)

    def test_search_by_title_exact_match(self):
        """Test searching announcements by exact title."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"search": "New Feature Release"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "New Feature Release")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"search": "SYSTEM"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_search_no_results(self):
        """Test search with no matching results."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"search": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_empty_string_returns_all(self):
        """Test that empty search string returns all announcements."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"search": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)


class AdminAnnouncementListOrderingTests(TestCase):
    """Tests for ordering functionality in admin announcement list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        now = timezone.now()
        self.announcement_low = create_announcement(
            "Low Priority",
            "Message",
            priority="low",
            start_date=now + timedelta(days=1)
        )
        self.announcement_high = create_announcement(
            "High Priority",
            "Message",
            priority="high",
            start_date=now + timedelta(days=2)
        )
        self.announcement_normal = create_announcement(
            "Normal Priority",
            "Message",
            priority="normal",
            start_date=now + timedelta(days=3)
        )

    def test_default_ordering_by_priority_and_created_at(self):
        """Test that default ordering is by -priority, -created_at.
        
        Note: Priority is stored as a string, so ordering is alphabetical.
        Descending alphabetical: 'normal' > 'low' > 'high'
        """
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Since priority is a string field, -priority orders alphabetically descending
        # 'normal' > 'low' > 'high' alphabetically, so 'normal' comes first
        self.assertEqual(response.data["results"][0]["priority"], "normal")

    def test_ordering_by_id_ascending(self):
        """Test ordering announcements by id ascending."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"ordering": "id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in response.data["results"]]
        self.assertEqual(ids, sorted(ids))

    def test_ordering_by_id_descending(self):
        """Test ordering announcements by id descending."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"ordering": "-id"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in response.data["results"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_ordering_by_start_date(self):
        """Test ordering announcements by start_date."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"ordering": "start_date"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Low priority has earliest start_date
        self.assertEqual(response.data["results"][0]["title"], "Low Priority")

    def test_ordering_by_is_active(self):
        """Test ordering announcements by is_active status."""
        self.announcement_low.is_active = False
        self.announcement_low.save()

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"ordering": "is_active"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inactive announcement (False) should come first
        self.assertFalse(response.data["results"][0]["is_active"])


class AdminAnnouncementListPaginationTests(TestCase):
    """Tests for pagination in admin announcement list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_default_page_size(self):
        """Test that default page size is 25."""
        for i in range(30):
            create_announcement(f"Announcement {i}", f"Message {i}")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_custom_page_size(self):
        """Test custom page_size parameter."""
        for i in range(15):
            create_announcement(f"Announcement {i}", f"Message {i}")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)

    def test_page_size_max_limit(self):
        """Test that page_size respects max limit of 100."""
        for i in range(105):
            create_announcement(f"Announcement {i}", f"Message {i}")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"page_size": 200})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data["results"]), 100)

    def test_pagination_second_page(self):
        """Test accessing the second page of results."""
        for i in range(30):
            create_announcement(f"Announcement {i}", f"Message {i}")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_page_returns_404(self):
        """Test that requesting an invalid page returns 404."""
        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL, {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminAnnouncementListEdgeCasesTests(TestCase):
    """Edge case tests for admin announcement list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_announcement_with_null_end_date(self):
        """Test that announcements with null end_date are listed."""
        create_announcement("No End Date", "Message", end_date=None)

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["results"][0]["end_date"])

    def test_announcement_with_end_date(self):
        """Test that announcements with end_date are listed correctly."""
        end_date = timezone.now() + timedelta(days=7)
        create_announcement("Has End Date", "Message", end_date=end_date)

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNotNone(response.data["results"][0]["end_date"])

    def test_different_priority_levels(self):
        """Test that all priority levels are listed."""
        create_announcement("Low", "Message", priority="low")
        create_announcement("Normal", "Message", priority="normal")
        create_announcement("High", "Message", priority="high")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

        priorities = [a["priority"] for a in response.data["results"]]
        self.assertIn("low", priorities)
        self.assertIn("normal", priorities)
        self.assertIn("high", priorities)

    def test_different_announcement_types(self):
        """Test that different announcement types are listed."""
        create_announcement("General", "Message", announcement_type="general")
        create_announcement("Welcome", "Message", announcement_type="welcome")
        create_announcement("Maintenance", "Message", announcement_type="maintenance")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

        types = [a["announcement_type"] for a in response.data["results"]]
        self.assertIn("general", types)
        self.assertIn("welcome", types)
        self.assertIn("maintenance", types)

    def test_superuser_can_access(self):
        """Test that superusers can also access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        create_announcement("Test", "Message")

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_past_start_date_announcement(self):
        """Test announcements with past start dates are listed."""
        past_date = timezone.now() - timedelta(days=30)
        create_announcement("Past Start", "Message", start_date=past_date)

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_future_start_date_announcement(self):
        """Test announcements with future start dates are listed."""
        future_date = timezone.now() + timedelta(days=30)
        create_announcement("Future Start", "Message", start_date=future_date)

        response = self.client.get(ADMIN_ANNOUNCEMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

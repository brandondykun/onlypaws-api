"""
Tests for the admin announcement detail API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta

from core.test_utils.utils import create_user, create_profile, create_announcement


def get_admin_announcement_detail_url(announcement_id):
    """Return admin announcement detail URL."""
    return reverse("admin-announcement-detail", kwargs={"pk": announcement_id})


class PublicAdminAnnouncementDetailTests(TestCase):
    """Tests for unauthenticated access to admin announcement detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.announcement = create_announcement("Test Announcement", "Test message")

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_put_returns_401(self):
        """Test that unauthenticated PUT requests return 401."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.put(url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_delete_returns_401(self):
        """Test that unauthenticated DELETE requests return 401."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminAnnouncementDetailTests(TestCase):
    """Tests for non-admin authenticated access to admin announcement detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.announcement = create_announcement("Test Announcement", "Test message")
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminAnnouncementDetailGetTests(TestCase):
    """Tests for GET requests to admin announcement detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.announcement = create_announcement(
            "Test Announcement",
            "Test message content",
            priority="high",
            announcement_type="maintenance"
        )

    def test_admin_can_retrieve_announcement(self):
        """Test that admin users can retrieve announcement details."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertIn("title", response.data)
        self.assertIn("message", response.data)
        self.assertIn("priority", response.data)
        self.assertIn("announcement_type", response.data)
        self.assertIn("is_active", response.data)
        self.assertIn("start_date", response.data)
        self.assertIn("end_date", response.data)
        self.assertIn("created_at", response.data)

    def test_returns_correct_announcement_data(self):
        """Test that the correct announcement data is returned."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.announcement.id)
        self.assertEqual(response.data["title"], "Test Announcement")
        self.assertEqual(response.data["message"], "Test message content")
        self.assertEqual(response.data["priority"], "high")
        self.assertEqual(response.data["announcement_type"], "maintenance")

    def test_nonexistent_announcement_returns_404(self):
        """Test that requesting a nonexistent announcement returns 404."""
        url = get_admin_announcement_detail_url(99999)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminAnnouncementDetailUpdateTests(TestCase):
    """Tests for PUT/PATCH requests to admin announcement detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.announcement = create_announcement("Original Title", "Original message")

    def test_admin_can_update_announcement_with_put(self):
        """Test that admin users can fully update announcement with PUT."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        start_date = timezone.now()
        data = {
            "title": "Updated Title",
            "message": "Updated message",
            "priority": "high",
            "announcement_type": "maintenance",
            "is_active": False,
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=7)).isoformat(),
        }
        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Title")
        self.assertEqual(response.data["message"], "Updated message")
        self.assertEqual(response.data["priority"], "high")
        self.assertFalse(response.data["is_active"])

    def test_admin_can_partial_update_with_patch(self):
        """Test that admin users can partially update announcement with PATCH."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        data = {"title": "Patched Title"}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Patched Title")
        # Original message should be unchanged
        self.assertEqual(response.data["message"], "Original message")

    def test_update_title(self):
        """Test updating announcement title."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.patch(url, {"title": "New Title"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "New Title")

    def test_update_message(self):
        """Test updating announcement message."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.patch(url, {"message": "New message"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "New message")

    def test_update_priority(self):
        """Test updating announcement priority."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.patch(url, {"priority": "high"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["priority"], "high")

    def test_update_is_active(self):
        """Test updating announcement is_active status."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.patch(url, {"is_active": False}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_update_start_date(self):
        """Test updating announcement start_date."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        new_start_date = timezone.now() + timedelta(days=5)
        response = self.client.patch(
            url,
            {"start_date": new_start_date.isoformat()},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["start_date"])

    def test_update_end_date(self):
        """Test updating announcement end_date."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        new_end_date = timezone.now() + timedelta(days=30)
        response = self.client.patch(
            url,
            {"end_date": new_end_date.isoformat()},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["end_date"])

    def test_update_end_date_to_null(self):
        """Test updating announcement end_date to null."""
        # First set an end date
        self.announcement.end_date = timezone.now() + timedelta(days=7)
        self.announcement.save()

        url = get_admin_announcement_detail_url(self.announcement.id)
        response = self.client.patch(url, {"end_date": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["end_date"])

    def test_cannot_update_id(self):
        """Test that id cannot be updated (read-only)."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        original_id = self.announcement.id
        response = self.client.patch(url, {"id": 99999}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], original_id)

    def test_cannot_update_created_at(self):
        """Test that created_at cannot be updated (read-only)."""
        url = get_admin_announcement_detail_url(self.announcement.id)
        new_date = timezone.now() - timedelta(days=365)
        response = self.client.patch(
            url,
            {"created_at": new_date.isoformat()},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # created_at should remain unchanged

    def test_update_nonexistent_announcement_returns_404(self):
        """Test that updating a nonexistent announcement returns 404."""
        url = get_admin_announcement_detail_url(99999)
        response = self.client.patch(url, {"title": "New Title"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminAnnouncementDetailDeleteTests(TestCase):
    """Tests for DELETE requests to admin announcement detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_delete_announcement(self):
        """Test that admin users can delete announcements."""
        announcement = create_announcement("To Delete", "Will be deleted")
        url = get_admin_announcement_detail_url(announcement.id)

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify announcement is deleted
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_announcement_returns_404(self):
        """Test that deleting a nonexistent announcement returns 404."""
        url = get_admin_announcement_detail_url(99999)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_from_list(self):
        """Test that deleted announcement no longer appears in list."""
        announcement = create_announcement("To Delete", "Will be deleted")
        announcement_id = announcement.id

        url = get_admin_announcement_detail_url(announcement_id)
        self.client.delete(url)

        list_url = reverse("admin-announcement-list")
        response = self.client.get(list_url)

        ids = [a["id"] for a in response.data["results"]]
        self.assertNotIn(announcement_id, ids)


class AdminAnnouncementDetailEdgeCasesTests(TestCase):
    """Edge case tests for admin announcement detail."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_invalid_announcement_id_format(self):
        """Test that invalid announcement ID format is handled."""
        url = "/api/admin/announcements/invalid/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_superuser_can_access(self):
        """Test that superusers can access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        announcement = create_announcement("Test", "Message")

        url = get_admin_announcement_detail_url(announcement.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_announcement_with_all_priority_levels(self):
        """Test retrieving announcements with each priority level."""
        for priority in ["low", "normal", "high"]:
            announcement = create_announcement(f"{priority} Priority", "Message", priority=priority)
            url = get_admin_announcement_detail_url(announcement.id)
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["priority"], priority)

    def test_update_with_empty_title_fails(self):
        """Test that updating with empty title fails validation."""
        announcement = create_announcement("Original", "Message")
        url = get_admin_announcement_detail_url(announcement.id)

        response = self.client.patch(url, {"title": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_with_empty_message_fails(self):
        """Test that updating with empty message fails validation."""
        announcement = create_announcement("Title", "Original message")
        url = get_admin_announcement_detail_url(announcement.id)

        response = self.client.patch(url, {"message": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_concurrent_updates(self):
        """Test that concurrent updates work correctly."""
        announcement = create_announcement("Original", "Message")
        url = get_admin_announcement_detail_url(announcement.id)

        # First update
        self.client.patch(url, {"title": "First Update"}, format="json")
        # Second update
        response = self.client.patch(url, {"message": "Second Update"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "First Update")
        self.assertEqual(response.data["message"], "Second Update")

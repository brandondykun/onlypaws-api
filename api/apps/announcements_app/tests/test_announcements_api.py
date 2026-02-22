"""
Tests for the announcements API endpoints.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework import status

from apps.announcements_app.models import Announcement, AnnouncementPriority
from core.test_utils.utils import create_user, create_profile
from .util import ANNOUNCEMENTS_LIST_URL


class PublicAnnouncementsApiTests(TestCase):
    """Test unauthenticated API requests to announcements endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required for announcements endpoint."""
        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_required_with_query_params(self):
        """Test that authentication is required even with query parameters."""
        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "true"})

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateAnnouncementsApiTests(TestCase):
    """Test authenticated API requests to announcements endpoint."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()

        # Create user and profile
        self.user = create_user(
            email="test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="testuser",
        )

        # Authenticate the client
        self.client.force_authenticate(user=self.user)

        # Set auth-profile-id header
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        # Store current time for testing
        self.now = timezone.now()

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_retrieve_announcements_empty(self):
        """Test retrieving announcements when none exist."""
        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_retrieve_active_announcement(self):
        """Test retrieving a single active announcement."""
        Announcement.objects.create(
            title="Test Announcement",
            message="This is a test announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Test Announcement")
        self.assertEqual(res.data[0]["message"], "This is a test announcement")
        self.assertEqual(res.data[0]["priority"], AnnouncementPriority.NORMAL)

    def test_retrieve_multiple_announcements(self):
        """Test retrieving multiple active announcements."""
        Announcement.objects.create(
            title="First Announcement",
            message="First message",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        Announcement.objects.create(
            title="Second Announcement",
            message="Second message",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_serializer_fields(self):
        """Test that serializer returns expected fields."""
        announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            priority=AnnouncementPriority.HIGH,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="maintenance",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        # Check expected fields are present
        self.assertIn("id", res.data[0])
        self.assertIn("title", res.data[0])
        self.assertIn("message", res.data[0])
        self.assertIn("priority", res.data[0])
        self.assertIn("announcement_type", res.data[0])
        self.assertIn("created_at", res.data[0])

        # Check field values
        self.assertEqual(res.data[0]["id"], announcement.id)
        self.assertEqual(res.data[0]["title"], "Test Announcement")
        self.assertEqual(res.data[0]["message"], "Test message")
        self.assertEqual(res.data[0]["priority"], AnnouncementPriority.HIGH)
        self.assertEqual(res.data[0]["announcement_type"], "maintenance")

    def test_inactive_announcement_not_returned(self):
        """Test that inactive announcements are not returned."""
        Announcement.objects.create(
            title="Inactive Announcement",
            message="Should not be visible",
            priority=AnnouncementPriority.NORMAL,
            is_active=False,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_future_announcement_not_returned(self):
        """Test that announcements with future start dates are not returned."""
        Announcement.objects.create(
            title="Future Announcement",
            message="Should not be visible yet",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now + timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_expired_announcement_not_returned(self):
        """Test that announcements past their end date are not returned."""
        Announcement.objects.create(
            title="Expired Announcement",
            message="Should no longer be visible",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=2),
            end_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_announcement_with_null_end_date_returned(self):
        """Test that announcements with null end dates are returned."""
        Announcement.objects.create(
            title="Perpetual Announcement",
            message="No end date",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            end_date=None,
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Perpetual Announcement")

    def test_announcement_at_start_date_boundary(self):
        """Test announcement exactly at start date is returned."""
        # Create announcement that starts exactly now
        Announcement.objects.create(
            title="Boundary Start Announcement",
            message="Starting now",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now,
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_announcement_at_end_date_boundary(self):
        """Test announcement at end date boundary is returned when end_date >= query time."""
        # Create announcement that ends in the near future to ensure it's still valid
        # when the query runs (accounts for small time differences)
        Announcement.objects.create(
            title="Boundary End Announcement",
            message="Ending soon",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            end_date=timezone.now() + timedelta(seconds=5),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)


class AnnouncementFilteringTests(TestCase):
    """Test announcement filtering functionality."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()

        # Create user and profile
        self.user = create_user(
            email="filter_test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="filteruser",
        )

        # Authenticate the client
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        self.now = timezone.now()

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_exclude_welcome_true(self):
        """Test exclude_welcome=true filters out welcome announcements."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "true"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "General Announcement")
        self.assertEqual(res.data[0]["announcement_type"], "general")

    def test_exclude_welcome_false(self):
        """Test exclude_welcome=false includes all announcements."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "false"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_exclude_welcome_not_provided(self):
        """Test that welcome announcements are included when param not provided."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_exclude_welcome_case_insensitive_true(self):
        """Test exclude_welcome is case insensitive for TRUE value."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "TRUE"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["announcement_type"], "general")

    def test_exclude_welcome_case_insensitive_mixed(self):
        """Test exclude_welcome is case insensitive for mixed case."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "True"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["announcement_type"], "general")

    def test_exclude_welcome_invalid_value_includes_all(self):
        """Test that invalid exclude_welcome values include all announcements."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="General Announcement",
            message="General info",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="general",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "invalid"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_exclude_welcome_empty_string_includes_all(self):
        """Test that empty exclude_welcome includes all announcements."""
        Announcement.objects.create(
            title="Welcome Announcement",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": ""})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_exclude_welcome_only_welcome_announcements(self):
        """Test exclude_welcome when only welcome announcements exist."""
        Announcement.objects.create(
            title="Welcome 1",
            message="Welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )
        Announcement.objects.create(
            title="Welcome 2",
            message="Also welcome!",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            announcement_type="welcome",
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {"exclude_welcome": "true"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)


class AnnouncementOrderingTests(TestCase):
    """Test announcement ordering functionality."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()

        # Create user and profile
        self.user = create_user(
            email="order_test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="orderuser",
        )

        # Authenticate the client
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        self.now = timezone.now()

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_ordering_by_priority(self):
        """Test announcements are ordered by priority (high > normal > low)."""
        # Create announcements with different priorities
        low = Announcement.objects.create(
            title="Low Priority",
            message="Low priority message",
            priority=AnnouncementPriority.LOW,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        normal = Announcement.objects.create(
            title="Normal Priority",
            message="Normal priority message",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        high = Announcement.objects.create(
            title="High Priority",
            message="High priority message",
            priority=AnnouncementPriority.HIGH,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 3)
        self.assertEqual(res.data[0]["title"], "High Priority")
        self.assertEqual(res.data[1]["title"], "Normal Priority")
        self.assertEqual(res.data[2]["title"], "Low Priority")

    def test_ordering_by_created_at_within_same_priority(self):
        """Test announcements with same priority are ordered by created_at descending."""
        # Create announcements with same priority, different created times
        first = Announcement.objects.create(
            title="First Created",
            message="Created first",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        # Small delay to ensure different created_at
        import time
        time.sleep(0.01)
        second = Announcement.objects.create(
            title="Second Created",
            message="Created second",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        # Second created should come first (descending order)
        self.assertEqual(res.data[0]["title"], "Second Created")
        self.assertEqual(res.data[1]["title"], "First Created")

    def test_combined_priority_and_created_at_ordering(self):
        """Test combined ordering: priority first, then created_at descending."""
        # Create low priority first
        low1 = Announcement.objects.create(
            title="Low 1",
            message="Low priority, created first",
            priority=AnnouncementPriority.LOW,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        import time
        time.sleep(0.01)
        # Create high priority second
        high1 = Announcement.objects.create(
            title="High 1",
            message="High priority, created second",
            priority=AnnouncementPriority.HIGH,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        time.sleep(0.01)
        # Create another high priority third
        high2 = Announcement.objects.create(
            title="High 2",
            message="High priority, created third",
            priority=AnnouncementPriority.HIGH,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        time.sleep(0.01)
        # Create low priority fourth
        low2 = Announcement.objects.create(
            title="Low 2",
            message="Low priority, created fourth",
            priority=AnnouncementPriority.LOW,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 4)
        # High priority first (by created_at descending)
        self.assertEqual(res.data[0]["title"], "High 2")
        self.assertEqual(res.data[1]["title"], "High 1")
        # Low priority last (by created_at descending)
        self.assertEqual(res.data[2]["title"], "Low 2")
        self.assertEqual(res.data[3]["title"], "Low 1")

    def test_all_priority_levels(self):
        """Test that all three priority levels are ordered correctly."""
        low = Announcement.objects.create(
            title="Low",
            message="Low priority",
            priority=AnnouncementPriority.LOW,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        normal = Announcement.objects.create(
            title="Normal",
            message="Normal priority",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        high = Announcement.objects.create(
            title="High",
            message="High priority",
            priority=AnnouncementPriority.HIGH,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        priorities = [item["priority"] for item in res.data]
        self.assertEqual(priorities, [
            AnnouncementPriority.HIGH,
            AnnouncementPriority.NORMAL,
            AnnouncementPriority.LOW,
        ])


class AnnouncementTypeTests(TestCase):
    """Test different announcement types."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()

        self.user = create_user(
            email="type_test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="typeuser",
        )

        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        self.now = timezone.now()

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_default_announcement_type(self):
        """Test that default announcement type is 'general'."""
        announcement = Announcement.objects.create(
            title="Default Type",
            message="Should have default type",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["announcement_type"], "general")

    def test_various_announcement_types(self):
        """Test that various announcement types are returned correctly."""
        types = ["general", "welcome", "maintenance", "feature", "update"]

        for i, announcement_type in enumerate(types):
            Announcement.objects.create(
                title=f"Announcement {i}",
                message=f"Type: {announcement_type}",
                priority=AnnouncementPriority.NORMAL,
                is_active=True,
                start_date=self.now - timedelta(hours=1),
                announcement_type=announcement_type,
            )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 5)

        returned_types = {item["announcement_type"] for item in res.data}
        self.assertEqual(returned_types, set(types))


class AnnouncementEdgeCasesTests(TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()

        self.user = create_user(
            email="edge_test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="edgeuser",
        )

        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        self.now = timezone.now()

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_mixed_active_inactive_announcements(self):
        """Test that only active announcements are returned in a mixed set."""
        Announcement.objects.create(
            title="Active 1",
            message="Active announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )
        Announcement.objects.create(
            title="Inactive 1",
            message="Inactive announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=False,
            start_date=self.now - timedelta(hours=1),
        )
        Announcement.objects.create(
            title="Active 2",
            message="Another active announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        titles = {item["title"] for item in res.data}
        self.assertEqual(titles, {"Active 1", "Active 2"})

    def test_mixed_time_periods(self):
        """Test filtering with mix of past, current, and future announcements."""
        # Past (expired)
        Announcement.objects.create(
            title="Expired",
            message="Expired announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(days=2),
            end_date=self.now - timedelta(days=1),
        )
        # Current
        Announcement.objects.create(
            title="Current",
            message="Current announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(hours=1),
        )
        # Future
        Announcement.objects.create(
            title="Future",
            message="Future announcement",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now + timedelta(days=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Current")

    def test_long_title_and_message(self):
        """Test announcements with long title and message are handled correctly."""
        long_title = "A" * 200  # Max length is 200
        long_message = "B" * 10000

        Announcement.objects.create(
            title=long_title,
            message=long_message,
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], long_title)
        self.assertEqual(res.data[0]["message"], long_message)

    def test_special_characters_in_content(self):
        """Test announcements with special characters are handled correctly."""
        Announcement.objects.create(
            title="Special <>&\"' Characters!",
            message="Message with emoji: 🐾🐕🐈 and HTML: <script>alert('xss')</script>",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Special <>&\"' Characters!")
        self.assertIn("🐾", res.data[0]["message"])

    def test_unicode_content(self):
        """Test announcements with unicode content."""
        Announcement.objects.create(
            title="多语言公告 - Multilingual",
            message="日本語テスト 한국어 테스트 العربية тест",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "多语言公告 - Multilingual")

    def test_multiple_query_params(self):
        """Test that unknown query params are ignored."""
        Announcement.objects.create(
            title="Test",
            message="Test message",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL, {
            "exclude_welcome": "false",
            "unknown_param": "value",
            "another_unknown": "123",
        })

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_no_pagination(self):
        """Test that pagination is disabled (pagination_class = None)."""
        # Create many announcements
        for i in range(25):
            Announcement.objects.create(
                title=f"Announcement {i}",
                message=f"Message {i}",
                priority=AnnouncementPriority.NORMAL,
                is_active=True,
                start_date=self.now - timedelta(hours=1),
            )

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should return all announcements, not paginated
        self.assertEqual(len(res.data), 25)
        # Response should be a list, not a dict with pagination keys
        self.assertIsInstance(res.data, list)


class AnnouncementAuthenticationTests(TestCase):
    """Test authentication edge cases for announcements."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.now = timezone.now()

        # Create an announcement
        Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            priority=AnnouncementPriority.NORMAL,
            is_active=True,
            start_date=self.now - timedelta(hours=1),
        )

    def tearDown(self):
        """Clean up after each test."""
        Announcement.objects.all().delete()

    def test_auth_required_even_with_profile_header(self):
        """Test that authentication is still required even with auth-profile-id header."""
        # Create user and profile
        user = create_user(email="test@example.com", password="testpass123")
        profile = create_profile(user=user, username="testuser")

        # Set header but don't authenticate
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        res = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_different_user_can_access(self):
        """Test that different authenticated users can access announcements."""
        # Create first user
        user1 = create_user(email="user1@example.com", password="testpass123")
        profile1 = create_profile(user=user1, username="user1")

        # Create second user
        user2 = create_user(email="user2@example.com", password="testpass123")
        profile2 = create_profile(user=user2, username="user2")

        # Test with first user
        self.client.force_authenticate(user=user1)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile1.public_id))
        res1 = self.client.get(ANNOUNCEMENTS_LIST_URL)

        # Test with second user
        self.client.force_authenticate(user=user2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile2.public_id))
        res2 = self.client.get(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        # Both should see the same announcement
        self.assertEqual(len(res1.data), 1)
        self.assertEqual(len(res2.data), 1)

    def test_post_method_not_allowed(self):
        """Test that POST method is not allowed on the list endpoint."""
        user = create_user(email="test@example.com", password="testpass123")
        profile = create_profile(user=user, username="testuser")

        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        res = self.client.post(ANNOUNCEMENTS_LIST_URL, {
            "title": "New Announcement",
            "message": "Should not be created",
        })

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_method_not_allowed(self):
        """Test that PUT method is not allowed on the list endpoint."""
        user = create_user(email="test@example.com", password="testpass123")
        profile = create_profile(user=user, username="testuser")

        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        res = self.client.put(ANNOUNCEMENTS_LIST_URL, {
            "title": "Updated Announcement",
        })

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_method_not_allowed(self):
        """Test that PATCH method is not allowed on the list endpoint."""
        user = create_user(email="test@example.com", password="testpass123")
        profile = create_profile(user=user, username="testuser")

        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        res = self.client.patch(ANNOUNCEMENTS_LIST_URL, {
            "title": "Patched Announcement",
        })

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_method_not_allowed(self):
        """Test that DELETE method is not allowed on the list endpoint."""
        user = create_user(email="test@example.com", password="testpass123")
        profile = create_profile(user=user, username="testuser")

        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        res = self.client.delete(ANNOUNCEMENTS_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


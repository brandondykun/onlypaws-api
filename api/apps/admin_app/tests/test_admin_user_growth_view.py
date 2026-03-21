"""
Tests for AdminUserGrowthView.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin_app.views import AdminTimeSeriesView
from core.test_utils.utils import create_user

User = get_user_model()

USER_GROWTH_URL = reverse("admin-user-growth")


class PublicAdminUserGrowthTests(TestCase):
    """Test unauthenticated and non-staff access to user growth endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        response = self.client.get(USER_GROWTH_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_user_returns_403(self):
        """Test that authenticated non-staff users are forbidden."""
        user = create_user("regular@example.com")
        self.client.force_authenticate(user=user)
        response = self.client.get(USER_GROWTH_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateAdminUserGrowthTests(TestCase):
    """Test authenticated staff access to user growth endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.staff_user = create_user(
            "staff@example.com", is_staff=True
        )
        self.client.force_authenticate(user=self.staff_user)

    def test_returns_200(self):
        """Test that staff users get a successful response."""
        response = self.client.get(USER_GROWTH_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_has_labels_and_counts(self):
        """Test that the response contains labels and counts arrays."""
        response = self.client.get(USER_GROWTH_URL)
        self.assertIn("labels", response.data)
        self.assertIn("counts", response.data)
        self.assertIsInstance(response.data["labels"], list)
        self.assertIsInstance(response.data["counts"], list)

    def test_labels_and_counts_same_length(self):
        """Test that labels and counts arrays have the same length."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-01", "end": "2025-06"}
        )
        self.assertEqual(
            len(response.data["labels"]), len(response.data["counts"])
        )

    def test_default_range_includes_staff_user(self):
        """Test that the default range includes the staff user created in setUp."""
        response = self.client.get(USER_GROWTH_URL)
        self.assertGreater(sum(response.data["counts"]), 0)

    def test_explicit_date_range(self):
        """Test filtering with explicit start and end params."""
        now = timezone.now()
        start = f"{now.year}-{now.month:02d}"
        end = start
        response = self.client.get(
            USER_GROWTH_URL, {"start": start, "end": end}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["labels"]), 1)
        # The staff user was created this month
        self.assertEqual(response.data["counts"][0], 1)

    def test_fills_zero_months(self):
        """Test that months with no users are filled with zero."""
        now = timezone.now()
        # Request a 3-month range; user was created in current month only
        start_dt = datetime.date(now.year, now.month, 1)
        # Go back 2 months
        month = now.month - 2
        year = now.year
        while month < 1:
            month += 12
            year -= 1
        start = f"{year}-{month:02d}"
        end = f"{now.year}-{now.month:02d}"

        response = self.client.get(
            USER_GROWTH_URL, {"start": start, "end": end}
        )
        self.assertEqual(len(response.data["labels"]), 3)
        self.assertEqual(len(response.data["counts"]), 3)
        # First two months should be zero, last should have the staff user
        self.assertEqual(response.data["counts"][0], 0)
        self.assertEqual(response.data["counts"][1], 0)
        self.assertEqual(response.data["counts"][2], 1)

    def test_multiple_users_same_month(self):
        """Test that multiple users in the same month are counted together."""
        create_user("user2@example.com")
        create_user("user3@example.com")
        now = timezone.now()
        start = f"{now.year}-{now.month:02d}"
        end = start

        response = self.client.get(
            USER_GROWTH_URL, {"start": start, "end": end}
        )
        # staff_user + 2 new users
        self.assertEqual(response.data["counts"][0], 3)

    def test_users_across_months(self):
        """Test that users in different months appear in separate buckets."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        now = timezone.now()
        # Create a user and backdate their created_at to last month
        old_user = create_user("old@example.com")
        month = now.month - 1
        year = now.year
        if month < 1:
            month = 12
            year -= 1
        old_user.created_at = now.replace(
            year=year, month=month, day=15,
            hour=0, minute=0, second=0, microsecond=0
        )
        old_user.save(update_fields=["created_at"])

        start = f"{year}-{month:02d}"
        end = f"{now.year}-{now.month:02d}"

        response = self.client.get(
            USER_GROWTH_URL, {"start": start, "end": end}
        )
        self.assertEqual(len(response.data["labels"]), 2)
        self.assertEqual(response.data["counts"][0], 1)  # old_user
        self.assertEqual(response.data["counts"][1], 1)  # staff_user

    def test_range_with_no_users(self):
        """Test that a date range with no users returns all zeros."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2020-01", "end": "2020-03"}
        )
        self.assertEqual(len(response.data["labels"]), 3)
        self.assertEqual(response.data["counts"], [0, 0, 0])

    def test_label_format(self):
        """Test that labels are formatted as 'Mon YYYY'."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-01", "end": "2025-03"}
        )
        self.assertEqual(response.data["labels"][0], "Jan 2025")
        self.assertEqual(response.data["labels"][1], "Feb 2025")
        self.assertEqual(response.data["labels"][2], "Mar 2025")

    def test_single_month_range(self):
        """Test requesting a single month returns exactly one entry."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-06", "end": "2025-06"}
        )
        self.assertEqual(len(response.data["labels"]), 1)
        self.assertEqual(len(response.data["counts"]), 1)

    def test_invalid_start_param_uses_default(self):
        """Test that an invalid start param falls back to default range."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "not-a-date", "end": "2025-12"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should fall back to default range, which includes data
        self.assertGreater(len(response.data["labels"]), 0)

    def test_invalid_end_param_uses_default(self):
        """Test that an invalid end param falls back to default range."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-01", "end": "bad"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["labels"]), 0)

    def test_both_params_invalid_uses_default(self):
        """Test that both params invalid falls back to default range."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "xyz", "end": "abc"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_only_start_param(self):
        """Test providing only start param uses current date as end."""
        now = timezone.now()
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Last label should be the current month
        last_label = response.data["labels"][-1]
        expected = now.strftime("%b %Y")
        self.assertEqual(last_label, expected)

    def test_only_end_param(self):
        """Test providing only end param uses earliest user as start."""
        response = self.client.get(
            USER_GROWTH_URL, {"end": "2026-12"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["labels"]), 0)
        self.assertGreater(sum(response.data["counts"]), 0)

    def test_year_boundary_range(self):
        """Test a range that spans a year boundary."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2024-11", "end": "2025-02"}
        )
        self.assertEqual(len(response.data["labels"]), 4)
        self.assertEqual(response.data["labels"][0], "Nov 2024")
        self.assertEqual(response.data["labels"][1], "Dec 2024")
        self.assertEqual(response.data["labels"][2], "Jan 2025")
        self.assertEqual(response.data["labels"][3], "Feb 2025")

    def test_counts_are_integers(self):
        """Test that all count values are integers."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "2025-01", "end": "2025-06"}
        )
        for count in response.data["counts"]:
            self.assertIsInstance(count, int)

    def test_post_method_not_allowed(self):
        """Test that POST requests are rejected."""
        response = self.client.post(USER_GROWTH_URL)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_put_method_not_allowed(self):
        """Test that PUT requests are rejected."""
        response = self.client.put(USER_GROWTH_URL)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_delete_method_not_allowed(self):
        """Test that DELETE requests are rejected."""
        response = self.client.delete(USER_GROWTH_URL)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )


class EmptyDatabaseUserGrowthTests(TestCase):
    """Test user growth endpoint when no users exist in the database.

    These tests exercise the _months_ago fallback in get_default_start,
    which only runs when the queryset returns no records.
    """

    def setUp(self):
        self.client = APIClient()
        self.staff_user = create_user(
            "staff@example.com", is_staff=True
        )
        self.client.force_authenticate(user=self.staff_user)
        # Delete all users so get_default_start falls back to _months_ago.
        # force_authenticate keeps auth for subsequent requests regardless.
        User.objects.all().delete()

    def test_no_start_param_uses_months_ago_fallback(self):
        """Test that omitting start with no users falls back to _months_ago default."""
        now = timezone.now()
        response = self.client.get(
            USER_GROWTH_URL, {"end": f"{now.year}-{now.month:02d}"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # _months_ago(now, 11) gives 12 months of range
        self.assertEqual(len(response.data["labels"]), 12)
        self.assertEqual(response.data["counts"], [0] * 12)

    def test_no_params_uses_months_ago_fallback(self):
        """Test that no params with no users falls back to _months_ago for start."""
        response = self.client.get(USER_GROWTH_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Default end is now, default start is _months_ago(now, 11)
        self.assertEqual(len(response.data["labels"]), 12)
        self.assertEqual(response.data["counts"], [0] * 12)

    def test_invalid_params_with_no_users_uses_months_ago_fallback(self):
        """Test that invalid params with no users triggers _months_ago via except block."""
        response = self.client.get(
            USER_GROWTH_URL, {"start": "bad", "end": "bad"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["labels"]), 12)
        self.assertEqual(response.data["counts"], [0] * 12)

    def test_months_ago_fallback_labels_start_correctly(self):
        """Test that the _months_ago fallback starts at the correct month."""
        now = timezone.now()
        response = self.client.get(USER_GROWTH_URL)
        # First label should be 11 months ago
        expected_start = AdminTimeSeriesView._months_ago(now, 11)
        expected_label = datetime.date(
            expected_start.year, expected_start.month, 1
        ).strftime("%b %Y")
        self.assertEqual(response.data["labels"][0], expected_label)
        # Last label should be current month
        expected_end = now.strftime("%b %Y")
        self.assertEqual(response.data["labels"][-1], expected_end)


class MonthsAgoUnitTests(TestCase):
    """Unit tests for AdminTimeSeriesView._months_ago static method."""

    def test_same_year(self):
        """Test going back months within the same year."""
        dt = datetime.datetime(2025, 6, 15, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 3)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 15)

    def test_crosses_year_boundary(self):
        """Test going back months across a year boundary."""
        dt = datetime.datetime(2025, 2, 10, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 3)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 11)
        self.assertEqual(result.day, 10)

    def test_crosses_multiple_years(self):
        """Test going back more than 12 months."""
        dt = datetime.datetime(2025, 3, 1, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 15)
        self.assertEqual(result.year, 2023)
        self.assertEqual(result.month, 12)

    def test_day_clamped_to_shorter_month(self):
        """Test that day is clamped when target month is shorter."""
        # March 31 → going back 1 month → Feb has 28 days
        dt = datetime.datetime(2025, 3, 31, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 1)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 28)

    def test_day_clamped_leap_year(self):
        """Test that day is clamped correctly for Feb in a leap year."""
        # March 31 → going back 1 month in a leap year → Feb has 29 days
        dt = datetime.datetime(2024, 3, 31, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 1)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 29)

    def test_zero_months(self):
        """Test going back zero months returns same year/month/day."""
        dt = datetime.datetime(2025, 6, 15, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 0)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 15)

    def test_preserves_timezone(self):
        """Test that timezone info is preserved."""
        dt = datetime.datetime(2025, 6, 15, tzinfo=datetime.timezone.utc)
        result = AdminTimeSeriesView._months_ago(dt, 3)
        self.assertEqual(result.tzinfo, datetime.timezone.utc)

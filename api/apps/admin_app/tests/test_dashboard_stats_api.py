"""
Tests for the admin dashboard stats API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.feedback_app.models import Feedback
from apps.moderation_app.models import PostReport
from core.test_utils.utils import (
    create_feedback,
    create_post,
    create_post_report,
    create_profile,
    create_report_reason,
    create_user,
)


ADMIN_STATS_URL = reverse("admin-dashboard-stats")


class PublicAdminDashboardStatsTests(TestCase):
    """Tests for unauthenticated access to admin stats endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_STATS_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminDashboardStatsTests(TestCase):
    """Tests for non-admin authenticated access to admin stats endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminDashboardStatsTests(TestCase):
    """Tests for admin access to the dashboard stats endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_stats(self):
        """Test that admin users can access the stats endpoint."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_all_required_fields(self):
        """Test that the response contains all expected stat fields."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("active_users_count", response.data)
        self.assertIn("total_profiles_count", response.data)
        self.assertIn("open_feedback_count", response.data)
        self.assertIn("pending_reports_count", response.data)

    def test_response_field_types_are_integers(self):
        """Test that all stat fields are integers."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data["active_users_count"], int)
        self.assertIsInstance(response.data["total_profiles_count"], int)
        self.assertIsInstance(response.data["open_feedback_count"], int)
        self.assertIsInstance(response.data["pending_reports_count"], int)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_STATS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_STATS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_STATS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_STATS_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AdminDashboardStatsActiveUsersTests(TestCase):
    """Tests for active_users_count stat."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_active_users_count_with_only_admin(self):
        """Test active users count when only admin user exists."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only the admin user should be counted
        self.assertEqual(response.data["active_users_count"], 1)

    def test_active_users_count_multiple_active_users(self):
        """Test active users count with multiple active users."""
        create_user("user1@example.com", "password123")
        create_user("user2@example.com", "password123")
        create_user("user3@example.com", "password123")

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 3 regular users = 4
        self.assertEqual(response.data["active_users_count"], 4)

    def test_active_users_count_excludes_inactive_users(self):
        """Test that inactive users are not counted."""
        create_user("active@example.com", "password123")

        inactive_user = create_user("inactive@example.com", "password123")
        inactive_user.is_active = False
        inactive_user.save()

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 1 active user = 2 (inactive user excluded)
        self.assertEqual(response.data["active_users_count"], 2)

    def test_active_users_count_with_all_inactive_except_admin(self):
        """Test active users count when all users except admin are inactive."""
        inactive_user1 = create_user("inactive1@example.com", "password123")
        inactive_user1.is_active = False
        inactive_user1.save()

        inactive_user2 = create_user("inactive2@example.com", "password123")
        inactive_user2.is_active = False
        inactive_user2.save()

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only admin is active
        self.assertEqual(response.data["active_users_count"], 1)


class AdminDashboardStatsProfilesTests(TestCase):
    """Tests for total_profiles_count stat."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_profiles_count_zero_with_no_profiles(self):
        """Test profiles count is zero when no profiles exist."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_profiles_count"], 0)

    def test_profiles_count_single_profile(self):
        """Test profiles count with a single profile."""
        user = create_user("user@example.com", "password123")
        create_profile("test_user", user, "About text")

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_profiles_count"], 1)

    def test_profiles_count_multiple_profiles(self):
        """Test profiles count with multiple profiles."""
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        user3 = create_user("user3@example.com", "password123")

        create_profile("user_1", user1, "About 1")
        create_profile("user_2", user2, "About 2")
        create_profile("user_3", user3, "About 3")

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_profiles_count"], 3)

    def test_profiles_count_includes_inactive_profiles(self):
        """Test that total profiles count includes inactive profiles."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("test_user", user, "About text")
        profile.is_active = False
        profile.save()

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inactive profiles should still be counted
        self.assertEqual(response.data["total_profiles_count"], 1)

    def test_profiles_count_multiple_profiles_per_user(self):
        """Test profiles count when a user has multiple profiles."""
        user = create_user("user@example.com", "password123")
        create_profile("profile_1", user, "About 1")
        create_profile("profile_2", user, "About 2")

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_profiles_count"], 2)


class AdminDashboardStatsFeedbackTests(TestCase):
    """Tests for open_feedback_count stat."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.regular_user = create_user("user@example.com", "password123")
        self.client.force_authenticate(user=self.admin_user)

    def test_open_feedback_count_zero_with_no_feedback(self):
        """Test open feedback count is zero when no feedback exists."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 0)

    def test_open_feedback_count_single_open(self):
        """Test open feedback count with a single open ticket."""
        create_feedback(
            title="Bug Report",
            description="Test bug",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 1)

    def test_open_feedback_count_multiple_open(self):
        """Test open feedback count with multiple open tickets."""
        for i in range(5):
            create_feedback(
                title=f"Bug Report {i}",
                description=f"Test bug {i}",
                ticket_type=Feedback.TicketType.BUG,
                reporter=self.regular_user,
                status=Feedback.FeedbackStatus.OPEN,
            )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 5)

    def test_open_feedback_count_excludes_in_progress(self):
        """Test that in-progress feedback is not counted as open."""
        create_feedback(
            title="Open Bug",
            description="Test open",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="In Progress Bug",
            description="Test in progress",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.IN_PROGRESS,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 1)

    def test_open_feedback_count_excludes_resolved(self):
        """Test that resolved feedback is not counted as open."""
        create_feedback(
            title="Open Bug",
            description="Test open",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="Resolved Bug",
            description="Test resolved",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.RESOLVED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 1)

    def test_open_feedback_count_excludes_closed(self):
        """Test that closed feedback is not counted as open."""
        create_feedback(
            title="Open Bug",
            description="Test open",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="Closed Bug",
            description="Test closed",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.CLOSED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 1)

    def test_open_feedback_count_excludes_duplicate(self):
        """Test that duplicate feedback is not counted as open."""
        create_feedback(
            title="Open Bug",
            description="Test open",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="Duplicate Bug",
            description="Test duplicate",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.DUPLICATE,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 1)

    def test_open_feedback_count_with_mixed_statuses(self):
        """Test open feedback count with all status types."""
        # Create one feedback for each status
        create_feedback(
            title="Open Bug",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="Open Feature",
            description="Test",
            ticket_type=Feedback.TicketType.FEATURE,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="In Progress",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.IN_PROGRESS,
        )
        create_feedback(
            title="Resolved",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.RESOLVED,
        )
        create_feedback(
            title="Closed",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.CLOSED,
        )
        create_feedback(
            title="Duplicate",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.DUPLICATE,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only 2 OPEN status feedback tickets
        self.assertEqual(response.data["open_feedback_count"], 2)

    def test_open_feedback_count_all_non_open(self):
        """Test that count is zero when all feedback is non-open."""
        create_feedback(
            title="In Progress",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.IN_PROGRESS,
        )
        create_feedback(
            title="Resolved",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.RESOLVED,
        )
        create_feedback(
            title="Closed",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=self.regular_user,
            status=Feedback.FeedbackStatus.CLOSED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["open_feedback_count"], 0)


class AdminDashboardStatsPendingReportsTests(TestCase):
    """Tests for pending_reports_count stat."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.regular_user = create_user("user@example.com", "password123")
        self.profile = create_profile("reporter_profile", self.regular_user, "About")
        self.post_owner = create_user("owner@example.com", "password123")
        self.post_owner_profile = create_profile("owner_profile", self.post_owner, "Owner about")
        self.post = create_post("Test post caption", self.post_owner_profile)
        self.report_reason = create_report_reason(
            "Inappropriate Content",
            "Content is inappropriate",
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_pending_reports_count_zero_with_no_reports(self):
        """Test pending reports count is zero when no reports exist."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 0)

    def test_pending_reports_count_single_pending(self):
        """Test pending reports count with a single pending report."""
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 1)

    def test_pending_reports_count_multiple_pending(self):
        """Test pending reports count with multiple pending reports."""
        # Create multiple posts and reports
        for i in range(4):
            user = create_user(f"reporter{i}@example.com", "password123")
            reporter_profile = create_profile(f"reporter_{i}", user, "About")
            create_post_report(
                post=self.post,
                reporter=reporter_profile,
                reason=self.report_reason,
                status=PostReport.ReportStatus.PENDING,
            )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 4)

    def test_pending_reports_count_excludes_under_review(self):
        """Test that under-review reports are not counted as pending."""
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        user2 = create_user("reporter2@example.com", "password123")
        profile2 = create_profile("reporter_2", user2, "About")
        post2 = create_post("Another post", self.post_owner_profile)
        create_post_report(
            post=post2,
            reporter=profile2,
            reason=self.report_reason,
            status=PostReport.ReportStatus.UNDER_REVIEW,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 1)

    def test_pending_reports_count_excludes_resolved(self):
        """Test that resolved reports are not counted as pending."""
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        user2 = create_user("reporter2@example.com", "password123")
        profile2 = create_profile("reporter_2", user2, "About")
        post2 = create_post("Another post", self.post_owner_profile)
        create_post_report(
            post=post2,
            reporter=profile2,
            reason=self.report_reason,
            status=PostReport.ReportStatus.RESOLVED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 1)

    def test_pending_reports_count_excludes_dismissed(self):
        """Test that dismissed reports are not counted as pending."""
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        user2 = create_user("reporter2@example.com", "password123")
        profile2 = create_profile("reporter_2", user2, "About")
        post2 = create_post("Another post", self.post_owner_profile)
        create_post_report(
            post=post2,
            reporter=profile2,
            reason=self.report_reason,
            status=PostReport.ReportStatus.DISMISSED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 1)

    def test_pending_reports_count_with_mixed_statuses(self):
        """Test pending reports count with all status types."""
        # Create reports for each status type
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        user2 = create_user("reporter2@example.com", "password123")
        profile2 = create_profile("reporter_2", user2, "About")
        post2 = create_post("Post 2", self.post_owner_profile)
        create_post_report(
            post=post2,
            reporter=profile2,
            reason=self.report_reason,
            status=PostReport.ReportStatus.PENDING,
        )

        user3 = create_user("reporter3@example.com", "password123")
        profile3 = create_profile("reporter_3", user3, "About")
        post3 = create_post("Post 3", self.post_owner_profile)
        create_post_report(
            post=post3,
            reporter=profile3,
            reason=self.report_reason,
            status=PostReport.ReportStatus.UNDER_REVIEW,
        )

        user4 = create_user("reporter4@example.com", "password123")
        profile4 = create_profile("reporter_4", user4, "About")
        post4 = create_post("Post 4", self.post_owner_profile)
        create_post_report(
            post=post4,
            reporter=profile4,
            reason=self.report_reason,
            status=PostReport.ReportStatus.RESOLVED,
        )

        user5 = create_user("reporter5@example.com", "password123")
        profile5 = create_profile("reporter_5", user5, "About")
        post5 = create_post("Post 5", self.post_owner_profile)
        create_post_report(
            post=post5,
            reporter=profile5,
            reason=self.report_reason,
            status=PostReport.ReportStatus.DISMISSED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only 2 PENDING status reports
        self.assertEqual(response.data["pending_reports_count"], 2)

    def test_pending_reports_count_all_non_pending(self):
        """Test that count is zero when all reports are non-pending."""
        create_post_report(
            post=self.post,
            reporter=self.profile,
            reason=self.report_reason,
            status=PostReport.ReportStatus.RESOLVED,
        )

        user2 = create_user("reporter2@example.com", "password123")
        profile2 = create_profile("reporter_2", user2, "About")
        post2 = create_post("Another post", self.post_owner_profile)
        create_post_report(
            post=post2,
            reporter=profile2,
            reason=self.report_reason,
            status=PostReport.ReportStatus.DISMISSED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_reports_count"], 0)


class AdminDashboardStatsIntegrationTests(TestCase):
    """Integration tests for the dashboard stats endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_empty_database_returns_zeros(self):
        """Test that an empty database returns zeros for all counts except active users."""
        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only admin user exists
        self.assertEqual(response.data["active_users_count"], 1)
        self.assertEqual(response.data["total_profiles_count"], 0)
        self.assertEqual(response.data["open_feedback_count"], 0)
        self.assertEqual(response.data["pending_reports_count"], 0)

    def test_all_stats_with_populated_database(self):
        """Test all stats with a fully populated database."""
        # Create users (3 active, 1 inactive)
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        user3 = create_user("user3@example.com", "password123")
        inactive_user = create_user("inactive@example.com", "password123")
        inactive_user.is_active = False
        inactive_user.save()

        # Create profiles
        profile1 = create_profile("user_1", user1, "About 1")
        profile2 = create_profile("user_2", user2, "About 2")
        profile3 = create_profile("user_3", user3, "About 3")

        # Create posts
        post1 = create_post("Post 1", profile1)
        post2 = create_post("Post 2", profile2)

        # Create feedback (2 open, 1 in_progress, 1 resolved)
        create_feedback(
            title="Open Bug 1",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=user1,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="Open Bug 2",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=user2,
            status=Feedback.FeedbackStatus.OPEN,
        )
        create_feedback(
            title="In Progress",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=user3,
            status=Feedback.FeedbackStatus.IN_PROGRESS,
        )
        create_feedback(
            title="Resolved",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=user1,
            status=Feedback.FeedbackStatus.RESOLVED,
        )

        # Create report reason
        reason = create_report_reason("Test Reason", "Test description")

        # Create reports (2 pending, 1 resolved)
        create_post_report(
            post=post1,
            reporter=profile2,
            reason=reason,
            status=PostReport.ReportStatus.PENDING,
        )
        create_post_report(
            post=post2,
            reporter=profile1,
            reason=reason,
            status=PostReport.ReportStatus.PENDING,
        )
        create_post_report(
            post=post1,
            reporter=profile3,
            reason=reason,
            status=PostReport.ReportStatus.RESOLVED,
        )

        response = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 3 active users = 4 (inactive excluded)
        self.assertEqual(response.data["active_users_count"], 4)
        # 3 profiles
        self.assertEqual(response.data["total_profiles_count"], 3)
        # 2 open feedback
        self.assertEqual(response.data["open_feedback_count"], 2)
        # 2 pending reports
        self.assertEqual(response.data["pending_reports_count"], 2)

    def test_stats_are_consistent_across_multiple_requests(self):
        """Test that stats remain consistent across multiple requests."""
        user = create_user("user@example.com", "password123")
        create_profile("test_user", user, "About")

        create_feedback(
            title="Open Bug",
            description="Test",
            ticket_type=Feedback.TicketType.BUG,
            reporter=user,
            status=Feedback.FeedbackStatus.OPEN,
        )

        # Make multiple requests
        response1 = self.client.get(ADMIN_STATS_URL)
        response2 = self.client.get(ADMIN_STATS_URL)
        response3 = self.client.get(ADMIN_STATS_URL)

        self.assertEqual(response1.data, response2.data)
        self.assertEqual(response2.data, response3.data)

    def test_stats_update_when_data_changes(self):
        """Test that stats update when underlying data changes."""
        # Initial request
        response1 = self.client.get(ADMIN_STATS_URL)
        initial_users = response1.data["active_users_count"]
        initial_profiles = response1.data["total_profiles_count"]

        # Add a new user (increases active_users_count)
        user = create_user("user@example.com", "password123")

        # Request again
        response2 = self.client.get(ADMIN_STATS_URL)
        self.assertEqual(response2.data["active_users_count"], initial_users + 1)
        self.assertEqual(response2.data["total_profiles_count"], initial_profiles)

        # Add a profile (increases total_profiles_count)
        create_profile("test_user", user, "About")

        # Request again
        response3 = self.client.get(ADMIN_STATS_URL)
        self.assertEqual(response3.data["active_users_count"], initial_users + 1)
        self.assertEqual(response3.data["total_profiles_count"], initial_profiles + 1)

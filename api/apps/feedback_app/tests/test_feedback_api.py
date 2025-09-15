from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from apps.feedback_app.models import Feedback, FeedbackComment

User = get_user_model()


class FeedbackAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test users
        self.regular_user = User.objects.create_user(
            email="user@example.com", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="testpass123", is_staff=True
        )

        # Create test feedback
        self.feedback = Feedback.objects.create(
            title="Test Bug Report",
            description="This is a test bug report",
            ticket_type="bug",
            reporter=self.regular_user,
        )

    def test_create_feedback_authenticated(self):
        """Test that authenticated users can create feedback"""
        self.client.force_authenticate(user=self.regular_user)

        data = {
            "title": "New Feature Request",
            "description": "Please add dark mode",
            "ticket_type": "feature",
            "app_version": "1.0.0",
            "device_info": {"platform": "iOS", "version": "15.0"},
        }

        response = self.client.post(reverse("feedback_app:feedback-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Feedback.objects.count(), 2)

        # Check that reporter is set to current user
        new_feedback = Feedback.objects.get(title="New Feature Request")
        self.assertEqual(new_feedback.reporter, self.regular_user)

    def test_create_feedback_unauthenticated(self):
        """Test that unauthenticated users cannot create feedback"""
        data = {
            "title": "New Feature Request",
            "description": "Please add dark mode",
            "ticket_type": "feature",
        }

        response = self.client.post(reverse("feedback_app:feedback-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_feedback_regular_user(self):
        """Test that regular users only see their own feedback"""
        # Create feedback from another user
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123"
        )
        Feedback.objects.create(
            title="Other User Feedback",
            description="This should not be visible",
            ticket_type="general",
            reporter=other_user,
        )

        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse("feedback_app:feedback-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Test Bug Report")

    def test_list_feedback_staff_user(self):
        """Test that staff users can see all feedback"""
        # Create feedback from another user
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123"
        )
        Feedback.objects.create(
            title="Other User Feedback",
            description="Staff should see this",
            ticket_type="general",
            reporter=other_user,
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(reverse("feedback_app:feedback-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_update_feedback_regular_user_forbidden(self):
        """Test that regular users cannot update feedback"""
        self.client.force_authenticate(user=self.regular_user)

        data = {"status": "resolved"}
        response = self.client.patch(reverse("feedback_app:feedback-detail", args=[self.feedback.id]), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_feedback_staff_user_allowed(self):
        """Test that staff users can update feedback"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "status": "in_progress",
            "priority": "high",
            "assignee": self.staff_user.id,
        }
        response = self.client.patch(reverse("feedback_app:feedback-detail", args=[self.feedback.id]), data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.status, "in_progress")
        self.assertEqual(self.feedback.priority, "high")
        self.assertEqual(self.feedback.assignee, self.staff_user)


class FeedbackCommentAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test users
        self.regular_user = User.objects.create_user(
            email="user@example.com", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="testpass123", is_staff=True
        )

        # Create test feedback
        self.feedback = Feedback.objects.create(
            title="Test Bug Report",
            description="This is a test bug report",
            ticket_type="bug",
            reporter=self.regular_user,
        )

        # Create test comment
        self.comment = FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="We are looking into this issue",
            is_internal=False,
        )

    def test_create_comment_staff_allowed(self):
        """Test that staff users can create comments"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "ticket": self.feedback.id,
            "content": "This has been fixed in the latest update",
            "is_internal": False,
        }

        response = self.client.post(reverse("feedback_app:feedback-comments-list"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FeedbackComment.objects.count(), 2)

    def test_create_comment_regular_user_forbidden(self):
        """Test that regular users cannot create comments"""
        self.client.force_authenticate(user=self.regular_user)

        data = {
            "ticket": self.feedback.id,
            "content": "Thanks for looking into this",
            "is_internal": False,
        }

        response = self.client.post(reverse("feedback_app:feedback-comments-list"), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_comments_regular_user_own_feedback(self):
        """Test that regular users can see non-internal comments on their own feedback"""
        # Create internal comment that should not be visible
        FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="Internal note: check with dev team",
            is_internal=True,
        )

        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse("feedback_app:feedback-comments-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see the non-internal comment
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["content"], "We are looking into this issue"
        )

    def test_list_comments_staff_sees_all(self):
        """Test that staff users can see all comments including internal ones"""
        # Create internal comment
        FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="Internal note: check with dev team",
            is_internal=True,
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(reverse("feedback_app:feedback-comments-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see both comments
        self.assertEqual(len(response.data["results"]), 2)

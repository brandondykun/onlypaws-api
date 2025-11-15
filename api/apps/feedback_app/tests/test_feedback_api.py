from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.feedback_app.models import Feedback, FeedbackComment

from .util import (
    FEEDBACK_LIST_URL,
    FEEDBACK_MY_TICKETS_URL,
    FEEDBACK_ASSIGNED_TO_ME_URL,
    FEEDBACK_COMMENTS_LIST_URL,
    feedback_detail_url,
    feedback_comments_detail_url,
    )


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

        response = self.client.post(FEEDBACK_LIST_URL, data, format="json")
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

        response = self.client.post(FEEDBACK_LIST_URL, data, format="json")
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
        response = self.client.get(FEEDBACK_LIST_URL)

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
        response = self.client.get(FEEDBACK_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_update_feedback_regular_user_forbidden(self):
        """Test that regular users cannot update feedback"""
        self.client.force_authenticate(user=self.regular_user)

        data = {"status": "resolved"}
        response = self.client.patch(feedback_detail_url(self.feedback.id), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_feedback_staff_user_allowed(self):
        """Test that staff users can update feedback"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "status": "in_progress",
            "priority": "high",
            "assignee": self.staff_user.id,
        }
        response = self.client.patch(feedback_detail_url(self.feedback.id), data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.status, "in_progress")
        self.assertEqual(self.feedback.priority, "high")
        self.assertEqual(self.feedback.assignee, self.staff_user)

    def test_full_update_feedback_regular_user_forbidden(self):
        """Test that regular users cannot perform full update on feedback"""
        self.client.force_authenticate(user=self.regular_user)

        data = {
            "title": "Updated Title",
            "description": "Updated description",
            "ticket_type": "feature",
            "status": "resolved",
        }
        response = self.client.put(feedback_detail_url(self.feedback.id), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_destroy_feedback_regular_user_forbidden(self):
        """Test that regular users cannot delete feedback"""
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.delete(feedback_detail_url(self.feedback.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify feedback still exists
        self.assertTrue(Feedback.objects.filter(id=self.feedback.id).exists())

    def test_destroy_feedback_staff_user_allowed(self):
        """Test that staff users can delete feedback"""
        self.client.force_authenticate(user=self.staff_user)

        feedback_id = self.feedback.id
        response = self.client.delete(feedback_detail_url(feedback_id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify feedback is deleted
        self.assertFalse(Feedback.objects.filter(id=feedback_id).exists())

    def test_filter_by_ticket_type(self):
        """Test filtering feedback by ticket_type"""
        # Create feedback with different ticket types
        Feedback.objects.create(
            title="Feature Request",
            description="New feature",
            ticket_type="feature",
            reporter=self.regular_user,
        )
        Feedback.objects.create(
            title="General Inquiry",
            description="Question about app",
            ticket_type="general",
            reporter=self.regular_user,
        )

        self.client.force_authenticate(user=self.regular_user)

        # Filter by bug
        response = self.client.get(FEEDBACK_LIST_URL, {"ticket_type": "bug"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["ticket_type"], "bug")

        # Filter by feature
        response = self.client.get(FEEDBACK_LIST_URL, {"ticket_type": "feature"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["ticket_type"], "feature")

    def test_filter_by_status(self):
        """Test filtering feedback by status"""
        # Update feedback to different statuses
        self.client.force_authenticate(user=self.staff_user)

        feedback2 = Feedback.objects.create(
            title="In Progress Ticket",
            description="Working on it",
            ticket_type="bug",
            reporter=self.regular_user,
            status="in_progress",
        )

        # Filter by open
        response = self.client.get(FEEDBACK_LIST_URL, {"status": "open"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "open")

        # Filter by in_progress
        response = self.client.get(FEEDBACK_LIST_URL, {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "in_progress")

    def test_filter_by_priority(self):
        """Test filtering feedback by priority"""
        self.client.force_authenticate(user=self.staff_user)

        # Create feedback with different priorities
        high_priority = Feedback.objects.create(
            title="High Priority Bug",
            description="Critical issue",
            ticket_type="bug",
            reporter=self.regular_user,
            priority="high",
        )
        low_priority = Feedback.objects.create(
            title="Low Priority Feature",
            description="Nice to have",
            ticket_type="feature",
            reporter=self.regular_user,
            priority="low",
        )

        # Filter by high priority
        response = self.client.get(FEEDBACK_LIST_URL, {"priority": "high"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["priority"], "high")

        # Filter by medium priority (default for self.feedback)
        response = self.client.get(FEEDBACK_LIST_URL, {"priority": "medium"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["priority"], "medium")

    def test_filter_by_assignee(self):
        """Test filtering feedback by assignee"""
        # Create another staff user
        staff_user2 = User.objects.create_user(
            email="staff2@example.com", password="testpass123", is_staff=True
        )

        # Assign feedback to different staff users
        self.feedback.assignee = self.staff_user
        self.feedback.save()

        feedback2 = Feedback.objects.create(
            title="Another Bug",
            description="Another issue",
            ticket_type="bug",
            reporter=self.regular_user,
            assignee=staff_user2,
        )

        self.client.force_authenticate(user=self.staff_user)

        # Filter by staff_user
        response = self.client.get(
            FEEDBACK_LIST_URL, {"assignee": str(self.staff_user.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.feedback.id)

        # Filter by staff_user2
        response = self.client.get(
            FEEDBACK_LIST_URL, {"assignee": str(staff_user2.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], feedback2.id)

    def test_filter_by_invalid_assignee(self):
        """Test filtering with invalid assignee ID returns empty queryset"""
        self.client.force_authenticate(user=self.staff_user)

        # Try with non-numeric assignee
        response = self.client.get(FEEDBACK_LIST_URL, {"assignee": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

        # Try with non-existent ID
        response = self.client.get(FEEDBACK_LIST_URL, {"assignee": "99999"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return results if there are any tickets with that assignee (none in this case)
        self.assertEqual(len(response.data["results"]), 0)

    def test_my_tickets_action(self):
        """Test the my_tickets custom action"""
        # Create feedback from another user
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123"
        )
        Feedback.objects.create(
            title="Other User Feedback",
            description="Should not appear",
            ticket_type="general",
            reporter=other_user,
        )

        # Create additional feedback for regular_user
        Feedback.objects.create(
            title="Another Bug",
            description="My second ticket",
            ticket_type="bug",
            reporter=self.regular_user,
        )

        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(FEEDBACK_MY_TICKETS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own tickets (2 total)
        self.assertEqual(len(response.data["results"]), 2)
        for ticket in response.data["results"]:
            self.assertEqual(ticket["reporter"]["id"], self.regular_user.id)

    def test_my_tickets_staff_user(self):
        """Test that staff users see only their own tickets with my_tickets action"""
        # Create feedback for staff user
        staff_feedback = Feedback.objects.create(
            title="Staff Bug Report",
            description="Bug reported by staff",
            ticket_type="bug",
            reporter=self.staff_user,
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(FEEDBACK_MY_TICKETS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see their own ticket
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], staff_feedback.id)

    def test_assigned_to_me_action(self):
        """Test the assigned_to_me custom action"""
        # Create another staff user
        staff_user2 = User.objects.create_user(
            email="staff2@example.com", password="testpass123", is_staff=True
        )

        # Assign feedback to staff users
        self.feedback.assignee = self.staff_user
        self.feedback.save()

        feedback2 = Feedback.objects.create(
            title="Another Bug",
            description="Assigned to staff2",
            ticket_type="bug",
            reporter=self.regular_user,
            assignee=staff_user2,
        )

        feedback3 = Feedback.objects.create(
            title="Third Bug",
            description="Also assigned to staff_user",
            ticket_type="bug",
            reporter=self.regular_user,
            assignee=self.staff_user,
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(FEEDBACK_ASSIGNED_TO_ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see tickets assigned to staff_user
        self.assertEqual(len(response.data["results"]), 2)
        for ticket in response.data["results"]:
            self.assertEqual(ticket["assignee"]["id"], self.staff_user.id)

    def test_assigned_to_me_regular_user_forbidden(self):
        """Test that regular users cannot access assigned_to_me action"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(FEEDBACK_ASSIGNED_TO_ME_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_to_me_no_assignments(self):
        """Test assigned_to_me when staff user has no assigned tickets"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(FEEDBACK_ASSIGNED_TO_ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return empty results
        self.assertEqual(len(response.data["results"]), 0)

    def test_combined_filters(self):
        """Test using multiple filters together"""
        self.client.force_authenticate(user=self.staff_user)

        # Create feedback with specific attributes
        Feedback.objects.create(
            title="High Priority Bug",
            description="Critical bug",
            ticket_type="bug",
            reporter=self.regular_user,
            priority="high",
            status="in_progress",
            assignee=self.staff_user,
        )

        Feedback.objects.create(
            title="High Priority Feature",
            description="Important feature",
            ticket_type="feature",
            reporter=self.regular_user,
            priority="high",
            status="open",
        )

        # Filter by multiple parameters
        response = self.client.get(
            FEEDBACK_LIST_URL,
            {
                "ticket_type": "bug",
                "priority": "high",
                "status": "in_progress",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "High Priority Bug")


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

        response = self.client.post(FEEDBACK_COMMENTS_LIST_URL, data)
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

        response = self.client.post(FEEDBACK_COMMENTS_LIST_URL, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify error message is present
        self.assertIn("detail", response.data)
        # Verify no comment was created
        self.assertEqual(FeedbackComment.objects.count(), 1)  # Only the setUp comment exists

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
        response = self.client.get(FEEDBACK_COMMENTS_LIST_URL)

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
        response = self.client.get(FEEDBACK_COMMENTS_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see both comments
        self.assertEqual(len(response.data["results"]), 2)

    def test_filter_by_ticket(self):
        """Test filtering comments by ticket ID"""
        # Create another feedback ticket with comments
        other_feedback = Feedback.objects.create(
            title="Another Bug Report",
            description="Different issue",
            ticket_type="bug",
            reporter=self.regular_user,
        )
        other_comment = FeedbackComment.objects.create(
            ticket=other_feedback,
            author=self.staff_user,
            content="Working on this one too",
            is_internal=False,
        )

        self.client.force_authenticate(user=self.staff_user)

        # Filter by first ticket
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"ticket": str(self.feedback.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.comment.id)

        # Filter by second ticket
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"ticket": str(other_feedback.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], other_comment.id)

    def test_filter_by_invalid_ticket(self):
        """Test filtering with invalid ticket ID returns empty queryset"""
        self.client.force_authenticate(user=self.staff_user)

        # Try with non-numeric ticket ID
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"ticket": "invalid"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

        # Try with non-existent ticket ID
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"ticket": "99999"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_filter_by_is_internal_staff_only(self):
        """Test that only staff can filter by is_internal parameter"""
        # Create both internal and non-internal comments
        internal_comment = FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="Internal note",
            is_internal=True,
        )

        # Staff user can filter by is_internal
        self.client.force_authenticate(user=self.staff_user)
        
        # Filter for non-internal comments
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"is_internal": "false"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["is_internal"], False)

        # Filter for internal comments
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"is_internal": "true"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["is_internal"], True)

    def test_filter_by_is_internal_regular_user_ignored(self):
        """Test that regular users cannot filter by is_internal parameter"""
        # Create internal comment
        FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="Internal note",
            is_internal=True,
        )

        self.client.force_authenticate(user=self.regular_user)

        # Regular user tries to filter by is_internal, but should still only see non-internal
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {"is_internal": "true"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still only see non-internal comments (filtered by permission, not query param)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["is_internal"], False)

    def test_update_comment_regular_user_forbidden(self):
        """Test that regular users cannot update comments"""
        self.client.force_authenticate(user=self.regular_user)

        data = {
            "content": "Updated content",
        }
        response = self.client.put(
            feedback_comments_detail_url(self.comment.id),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify content hasn't changed
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "We are looking into this issue")

    def test_update_comment_staff_allowed(self):
        """Test that staff users can update comments"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "ticket": self.feedback.id,
            "content": "Updated: Issue has been resolved",
            "is_internal": False,
        }
        response = self.client.put(
            feedback_comments_detail_url(self.comment.id),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify content has changed
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "Updated: Issue has been resolved")

    def test_partial_update_comment_regular_user_forbidden(self):
        """Test that regular users cannot partially update comments"""
        self.client.force_authenticate(user=self.regular_user)

        data = {
            "content": "Partially updated content",
        }
        response = self.client.patch(
            feedback_comments_detail_url(self.comment.id),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify content hasn't changed
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "We are looking into this issue")

    def test_partial_update_comment_staff_allowed(self):
        """Test that staff users can partially update comments"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "content": "Partially updated: Still investigating",
        }
        response = self.client.patch(
            feedback_comments_detail_url(self.comment.id),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify content has changed
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "Partially updated: Still investigating")

    def test_destroy_comment_regular_user_forbidden(self):
        """Test that regular users cannot delete comments"""
        self.client.force_authenticate(user=self.regular_user)

        comment_id = self.comment.id
        response = self.client.delete(
            feedback_comments_detail_url(comment_id)
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify comment still exists
        self.assertTrue(FeedbackComment.objects.filter(id=comment_id).exists())

    def test_destroy_comment_staff_allowed(self):
        """Test that staff users can delete comments"""
        self.client.force_authenticate(user=self.staff_user)

        comment_id = self.comment.id
        response = self.client.delete(
            feedback_comments_detail_url(comment_id)
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify comment is deleted
        self.assertFalse(FeedbackComment.objects.filter(id=comment_id).exists())

    def test_regular_user_cannot_see_other_users_comments(self):
        """Test that regular users cannot see comments on other users' tickets"""
        # Create another user and their feedback
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123"
        )
        other_feedback = Feedback.objects.create(
            title="Other User Bug",
            description="Other user issue",
            ticket_type="bug",
            reporter=other_user,
        )
        other_comment = FeedbackComment.objects.create(
            ticket=other_feedback,
            author=self.staff_user,
            content="Response to other user",
            is_internal=False,
        )

        # Regular user should not see comments on other users' tickets
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(FEEDBACK_COMMENTS_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see comments on their own ticket
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.comment.id)

    def test_combined_filters_staff(self):
        """Test using multiple filters together as staff user"""
        # Create another feedback ticket
        other_feedback = Feedback.objects.create(
            title="Another Bug Report",
            description="Different issue",
            ticket_type="bug",
            reporter=self.regular_user,
        )

        # Create comments with different properties
        FeedbackComment.objects.create(
            ticket=self.feedback,
            author=self.staff_user,
            content="Internal note for first ticket",
            is_internal=True,
        )
        FeedbackComment.objects.create(
            ticket=other_feedback,
            author=self.staff_user,
            content="Public comment for second ticket",
            is_internal=False,
        )

        self.client.force_authenticate(user=self.staff_user)

        # Filter by ticket and is_internal
        response = self.client.get(
            FEEDBACK_COMMENTS_LIST_URL,
            {
                "ticket": str(self.feedback.id),
                "is_internal": "true",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["content"], "Internal note for first ticket")

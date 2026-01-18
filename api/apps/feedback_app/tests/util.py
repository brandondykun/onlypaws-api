"""
Test utilities for feedback app.
"""

from django.urls import reverse

FEEDBACK_LIST_URL = reverse("feedback_app:feedback-list")
FEEDBACK_COMMENTS_LIST_URL = reverse("feedback_app:feedback-comments-list")
FEEDBACK_ASSIGNED_TO_ME_URL = reverse("feedback_app:feedback-assigned-to-me")
FEEDBACK_MY_TICKETS_URL = reverse("feedback_app:feedback-my-tickets")
FEEDBACK_ALL_TICKETS_URL = reverse("feedback_app:feedback-all-tickets")


def feedback_detail_url(feedback_id: int):
    """Create and return a feedback detail url.

    Parameters
    ----------
    feedback_id : int
        The id of the Feedback to detail.
    """
    return reverse("feedback_app:feedback-detail", args=[feedback_id])


def feedback_comments_detail_url(comment_id: int):
    """Create and return a feedback comments detail url.

    Parameters
    ----------
    comment_id : int
        The id of the FeedbackComment to detail.
    """
    return reverse("feedback_app:feedback-comments-detail", args=[comment_id])
"""
Test utilities for moderation app.
"""

from django.urls import reverse


REPORT_REASON_LIST_URL = reverse("moderation_app:report-reason-list")
REPORT_LIST_URL = reverse("moderation_app:report-list")
MY_REPORTS_URL = reverse("moderation_app:report-my-reports")
REPORTED_POSTS_URL = reverse("moderation_app:report-reported-posts")
BLOCK_PROFILE_URL = reverse("moderation_app:block-profile")
LIST_BLOCKED_PROFILES_URL = reverse("moderation_app:list-blocked-profiles")


def report_resolve_url(pk):
    """Generate URL for resolving a specific report"""
    return reverse("moderation_app:report-resolve", kwargs={"pk": pk})


def unblock_profile_url(public_id):
    """Generate URL for unblocking a specific profile"""
    return reverse("moderation_app:unblock-profile", kwargs={"public_id": public_id})


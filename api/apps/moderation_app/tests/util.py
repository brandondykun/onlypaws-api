"""
Test utilities for moderation app.
"""

from django.urls import reverse


REPORT_REASON_LIST_URL = reverse("moderation_app:report-reason-list")
REPORT_LIST_URL = reverse("moderation_app:report-list")
MY_REPORTS_URL = reverse("moderation_app:report-my-reports")
REPORTED_POSTS_URL = reverse("moderation_app:report-reported-posts")


def report_resolve_url(pk):
    """Generate URL for resolving a specific report"""
    return reverse("moderation_app:report-resolve", kwargs={"pk": pk})


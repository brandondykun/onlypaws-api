"""
Moderation app models.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class ReportReason(models.Model):
    """
    Model to store predefined reasons for reporting posts
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class PostReport(models.Model):
    """
    Model to store reports made by users on posts
    """

    class ReportStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending Review")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under Review")
        RESOLVED = "RESOLVED", _("Resolved")
        DISMISSED = "DISMISSED", _("Dismissed")

    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        "user_app.Profile", on_delete=models.SET_NULL, null=True, related_name="reported_posts"
    )
    reason = models.ForeignKey("moderation_app.ReportReason", on_delete=models.PROTECT)
    details = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        "user_app.Profile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="resolved_reports",
        blank=True,
    )
    resolution_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        # Prevent multiple reports from the same user on the same post
        unique_together = (("post", "reporter"),)

    def __str__(self):
        return f"Report on {self.post} by {self.reporter}"


"""
Moderation app models.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Block(models.Model):
    """
    Model to store profile blocks. When a block exists, neither profile
    should see the other's content anywhere in the app.
    """

    blocker = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="blocks_given",
    )
    blocked = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("blocker", "blocked"),)
        indexes = [
            models.Index(fields=["blocker"]),
            models.Index(fields=["blocked"]),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


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

    post = models.ForeignKey(
        "posts_app.Post", on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reported_posts",
    )
    reason = models.ForeignKey("moderation_app.ReportReason", on_delete=models.PROTECT)
    details = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        "profile_app.Profile",
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


class ProfileReportReason(models.Model):
    """
    Model to store predefined reasons for reporting profiles.
    Separate from ReportReason so profile-specific reasons can be managed independently.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class ProfileReport(models.Model):
    """
    Model to store reports made by users on profiles.
    """

    class ReportStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending Review")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under Review")
        RESOLVED = "RESOLVED", _("Resolved")
        DISMISSED = "DISMISSED", _("Dismissed")

    profile = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="profile_reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reported_profiles",
    )
    reason = models.ForeignKey(
        "moderation_app.ProfileReportReason", on_delete=models.PROTECT
    )
    details = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="resolved_profile_reports",
        blank=True,
    )
    resolution_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("profile", "reporter"),)

    def __str__(self):
        return f"Profile report on {self.profile} by {self.reporter}"


class ProfanityLog(models.Model):
    """
    Log of profanity detections for monitoring and tuning the profanity service.
    """

    class ContentType(models.TextChoices):
        CAPTION = "CAPTION", _("Caption")
        COMMENT = "COMMENT", _("Comment")
        USERNAME = "USERNAME", _("Username")
        ABOUT = "ABOUT", _("About Text")
        NAME = "NAME", _("Name")
        BREED = "BREED", _("Breed")
        PRE_UPLOAD_CHECK = "PRE_UPLOAD_CHECK", _("Pre-Upload Text Check")

    class DetectionMethod(models.TextChoices):
        ML = "ML", _("ML Probability")
        WORD_MATCH = "WORD_MATCH", _("Exact Word Match")
        SUBSTRING = "SUBSTRING", _("Substring Match")
        SHORT_MATCH = "SHORT_MATCH", _("Start/End Match")
        FUZZY = "FUZZY", _("Fuzzy Match")

    original_text = models.TextField()
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    detection_method = models.CharField(max_length=20, choices=DetectionMethod.choices)
    detection_details = models.JSONField(default=dict)
    profile = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profanity_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type"]),
            models.Index(fields=["detection_method"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"ProfanityLog #{self.id} [{self.content_type}] {self.detection_method}"

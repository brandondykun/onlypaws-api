from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Feedback(models.Model):
    class TicketType(models.TextChoices):
        FEATURE = "feature", _("Feature Request")
        BUG = "bug", _("Bug Report")
        GENERAL = "general", _("General")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        CRITICAL = "critical", _("Critical")

    class FeedbackStatus(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In Progress")
        RESOLVED = "resolved", _("Resolved")
        CLOSED = "closed", _("Closed")
        DUPLICATE = "duplicate", _("Duplicate")

    # Core fields
    title = models.CharField(max_length=200)
    description = models.TextField()
    ticket_type = models.CharField(max_length=20, choices=TicketType.choices)
    status = models.CharField(max_length=20, choices=FeedbackStatus.choices, default=FeedbackStatus.OPEN)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )

    # User relationship - using the custom User model
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_tickets",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # App context
    app_version = models.CharField(max_length=20, blank=True)
    device_info = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} - {self.title}"


class FeedbackComment(models.Model):
    ticket = models.ForeignKey(
        Feedback, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    is_internal = models.BooleanField(default=False)  # For admin-only comments
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on #{self.ticket.id} by {self.author.email}"

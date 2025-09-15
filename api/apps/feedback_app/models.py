from django.db import models
from django.conf import settings


class Feedback(models.Model):
    TICKET_TYPES = [
        ("feature", "Feature Request"),
        ("bug", "Bug Report"),
        ("general", "General"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("duplicate", "Duplicate"),
    ]

    # Core fields
    title = models.CharField(max_length=200)
    description = models.TextField()
    ticket_type = models.CharField(max_length=20, choices=TICKET_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="medium"
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

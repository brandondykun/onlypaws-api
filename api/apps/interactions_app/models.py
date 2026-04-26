"""
Interactions app models.
"""

import ulid
from django.core.validators import MinValueValidator
from django.db import models
from django_ulid.models import ULIDField


class Like(models.Model):
    profile = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="likes"
    )
    post = models.ForeignKey(
        "posts_app.Post", on_delete=models.CASCADE, related_name="likes"
    )
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.post}"

    class Meta:
        unique_together = (("profile", "post"),)


class Comment(models.Model):
    text = models.CharField(max_length=1000)
    profile = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="comments"
    )
    post = models.ForeignKey(
        "posts_app.Post", on_delete=models.CASCADE, related_name="comments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="all_replies",
        null=True,
        blank=True,
    )
    reply_to_comment = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True
    )

    def __str__(self):
        return self.text


class CommentLike(models.Model):
    profile = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="comment_likes"
    )
    comment = models.ForeignKey(
        "interactions_app.Comment", on_delete=models.CASCADE, related_name="likes"
    )
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.comment}"

    class Meta:
        unique_together = (("profile", "comment"),)


class Follow(models.Model):
    followed = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="following"
    )
    followed_by = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="followers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.followed_by.username} follows {self.followed.username}"

    class Meta:
        unique_together = (("followed", "followed_by"),)


class FollowRequest(models.Model):
    """Model for follow requests to private profiles."""

    requester = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="sent_follow_requests",
    )
    target = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="received_follow_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.requester.username} requested to follow {self.target.username}"

    class Meta:
        unique_together = (("requester", "target"),)


class PostInteraction(models.Model):
    """
    Append-only log of profile interactions with posts.

    Captures lightweight engagement signals (preview clicks, views, dwell)
    in addition to the higher-intent actions already tracked in their own
    state tables (Like, SavedPost, Comment). Used as the source of truth
    for building short-term user preference embeddings.

    This is an event log, not a state table: the same (profile, post,
    interaction_type) tuple can appear many times.
    """

    class InteractionType(models.TextChoices):
        PREVIEW_CLICK = "preview_click", "Preview Click"
        VIEW = "view", "View"
        LIKE = "like", "Like"
        SAVE = "save", "Save"
        COMMENT = "comment", "Comment"

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    profile = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="post_interactions",
    )
    post = models.ForeignKey(
        "posts_app.Post",
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    interaction_type = models.CharField(
        max_length=32,
        choices=InteractionType.choices,
    )
    dwell_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Time spent on the post in milliseconds. Only populated for VIEW interactions.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["profile", "-created_at"]),
            models.Index(fields=["post", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.profile_id} {self.interaction_type} post {self.post_id}"

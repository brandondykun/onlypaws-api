"""
Interactions app models.
"""
from django.db import models


class Like(models.Model):
    profile = models.ForeignKey("profile_app.Profile", on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="likes")
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
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="comments")
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
    comment = models.ForeignKey("interactions_app.Comment", on_delete=models.CASCADE, related_name="likes")
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
        "profile_app.Profile", on_delete=models.CASCADE, related_name="sent_follow_requests"
    )
    target = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="received_follow_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.requester.username} requested to follow {self.target.username}"

    class Meta:
        unique_together = (("requester", "target"),)


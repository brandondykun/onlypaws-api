import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.interactions_app.models import Like, CommentLike, Follow, Comment, FollowRequest
from apps.posts_app.models import PostImageTag
from .tasks import (
    create_post_like_notification_task,
    create_comment_like_notification_task,
    create_follow_notification_task,
    create_comment_notification_task,
    create_tagged_post_notification_task,
    create_follow_request_notification_task,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Like)
def handle_like_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a Like is created.
    Triggers notification creation via Celery task.
    """
    if created:  # Only trigger for new likes, not updates
        try:
            # Trigger async notification creation
            create_post_like_notification_task.delay(
                post_id=instance.post.id,
                liker_profile_id=instance.profile.id
            )
            logger.info(f"Like notification task queued for post {instance.post.id}")
        except Exception as e:
            logger.error(f"Error queuing like notification task: {e}")


@receiver(post_save, sender=CommentLike)
def handle_comment_like_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a CommentLike is created.
    Triggers notification creation via Celery task.
    """
    if created:  # Only trigger for new comment likes, not updates
        try:
            # Trigger async notification creation
            create_comment_like_notification_task.delay(
                comment_id=instance.comment.id,
                liker_profile_id=instance.profile.id
            )
            logger.info(f"Comment like notification task queued for comment {instance.comment.id}")
        except Exception as e:
            logger.error(f"Error queuing comment like notification task: {e}")


@receiver(post_save, sender=Comment)
def handle_comment_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a Comment is created.
    Triggers notification creation via Celery task.
    """
    if created:  # Only trigger for new comments, not updates
        try:
            # Trigger async notification creation
            create_comment_notification_task.delay(
                comment_id=instance.id,
                post_id=instance.post.id,
                commenter_profile_id=instance.profile.id
            )
            logger.info(f"Comment notification task queued for comment {instance.id} on post {instance.post.id}")
        except Exception as e:
            logger.error(f"Error queuing comment notification task: {e}")


@receiver(post_save, sender=Follow)
def handle_follow_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a Follow is created.
    Triggers notification creation via Celery task.
    Skip notification for private profiles since they receive follow request notifications.
    """
    if created:  # Only trigger for new follows, not updates
        # Skip notification for private profiles - they already received
        # a follow request notification and explicitly accepted it
        if instance.followed.is_private:
            logger.info(
                f"Skipping follow notification for private profile {instance.followed.username}"
            )
            return

        try:
            # Trigger async notification creation
            create_follow_notification_task.delay(
                followed_profile_id=instance.followed.id,
                follower_profile_id=instance.followed_by.id
            )
            logger.info(f"Follow notification task queued for {instance.followed_by.username} following {instance.followed.username}")
        except Exception as e:
            logger.error(f"Error queuing follow notification task: {e}")


@receiver(post_save, sender=PostImageTag)
def handle_post_image_tag_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a PostImageTag is created.
    Triggers notification creation via Celery task to notify the tagged profile.
    """
    if created:  # Only trigger for new tags, not updates
        try:
            # Trigger async notification creation
            create_tagged_post_notification_task.delay(
                post_image_tag_id=instance.id
            )
            logger.info(f"Tagged post notification task queued for {instance.tagged_profile.username} tagged by {instance.tagged_by_profile.username}")
        except Exception as e:
            logger.error(f"Error queuing tagged post notification task: {e}")


@receiver(post_save, sender=FollowRequest)
def handle_follow_request_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a FollowRequest is created.
    Triggers notification creation via Celery task to notify the target profile.
    """
    if created:  # Only trigger for new follow requests, not updates
        try:
            # Trigger async notification creation
            create_follow_request_notification_task.delay(
                follow_request_id=instance.id
            )
            logger.info(f"Follow request notification task queued for {instance.target.username} from {instance.requester.username}")
        except Exception as e:
            logger.error(f"Error queuing follow request notification task: {e}")


def disconnect_notification_signals():
    """Disconnect all notification signal handlers (e.g. during fixture loading)."""
    post_save.disconnect(handle_like_created, sender=Like)
    post_save.disconnect(handle_comment_like_created, sender=CommentLike)
    post_save.disconnect(handle_comment_created, sender=Comment)
    post_save.disconnect(handle_follow_created, sender=Follow)
    post_save.disconnect(handle_post_image_tag_created, sender=PostImageTag)
    post_save.disconnect(handle_follow_request_created, sender=FollowRequest)


def reconnect_notification_signals():
    """Reconnect all notification signal handlers after fixture loading."""
    post_save.connect(handle_like_created, sender=Like)
    post_save.connect(handle_comment_like_created, sender=CommentLike)
    post_save.connect(handle_comment_created, sender=Comment)
    post_save.connect(handle_follow_created, sender=Follow)
    post_save.connect(handle_post_image_tag_created, sender=PostImageTag)
    post_save.connect(handle_follow_request_created, sender=FollowRequest)

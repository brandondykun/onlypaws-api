import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core_app.models import Like, CommentLike, Follow, Comment
from .tasks import create_post_like_notification_task, create_comment_like_notification_task, create_follow_notification_task, create_comment_notification_task

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
    """
    if created:  # Only trigger for new follows, not updates
        try:
            # Trigger async notification creation
            create_follow_notification_task.delay(
                followed_profile_id=instance.followed.id,
                follower_profile_id=instance.followed_by.id
            )
            logger.info(f"Follow notification task queued for {instance.followed_by.username} following {instance.followed.username}")
        except Exception as e:
            logger.error(f"Error queuing follow notification task: {e}")

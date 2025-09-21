import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core_app.models import Like
from .tasks import create_post_like_notification_task

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

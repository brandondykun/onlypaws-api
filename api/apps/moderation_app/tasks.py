"""
Celery tasks for the moderation app.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def log_profanity_detection_task(
    self, original_text, content_type, detection_method, detection_details, profile_id=None
):
    """Log a profanity detection asynchronously. Best-effort — no retries."""
    from apps.moderation_app.models import ProfanityLog

    try:
        ProfanityLog.objects.create(
            original_text=original_text,
            content_type=content_type,
            detection_method=detection_method,
            detection_details=detection_details,
            profile_id=profile_id,
        )
        logger.info(
            f"Profanity logged: method={detection_method}, type={content_type}, profile={profile_id}"
        )
    except Exception as e:
        logger.error(f"Error logging profanity detection: {e}")

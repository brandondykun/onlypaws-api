"""
Celery tasks for the interactions app.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import PostInteraction

logger = logging.getLogger(__name__)


# Chunk size for the retention cleanup. Each chunk runs in its own DELETE
# statement so a single sweep never holds a long-running lock on the table.
CLEANUP_CHUNK_SIZE = 5000
# Hard upper bound on chunks per task invocation, so a runaway condition
# (clock skew, retention bumped to a much smaller value, etc.) cannot keep
# the task running indefinitely. Beat will pick up any leftover rows tomorrow.
MAX_CHUNKS_PER_RUN = 200


@shared_task(bind=True, ignore_result=True)
def cleanup_old_post_interactions_task(self, retention_days: int = 30):
    """
    Delete PostInteraction rows older than `retention_days` in chunks.

    Args:
        retention_days: Rows with `created_at < now - retention_days` are deleted.
                        Default 30; bump to 60 from the beat schedule when ready.
    """
    cutoff = timezone.now() - timedelta(days=retention_days)
    total_deleted = 0

    for _ in range(MAX_CHUNKS_PER_RUN):
        ids = list(
            PostInteraction.objects.filter(created_at__lt=cutoff)
            .order_by("id")
            .values_list("id", flat=True)[:CLEANUP_CHUNK_SIZE]
        )
        if not ids:
            break
        deleted, _ = PostInteraction.objects.filter(id__in=ids).delete()
        total_deleted += deleted

    logger.info(
        f"PostInteraction retention sweep: deleted={total_deleted} "
        f"retention_days={retention_days}"
    )
    return {"deleted": total_deleted, "retention_days": retention_days}

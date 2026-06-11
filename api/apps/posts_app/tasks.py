"""
Celery tasks for the posts app.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.core_app.image_placeholders import generate_blurhash_for_post_image
from .models import Post, PostImage

logger = logging.getLogger(__name__)


# Images are only considered once their post is old enough that its image-processing
# pipeline (process_post_images_task) has certainly finished. A freshly created
# post may legitimately still have images missing a blurhash because that task is in
# flight, and we don't want to race it.
BLURHASH_MIN_AGE_MINUTES = 10
# Upper bound on images handled per run so a large backlog (or an image that fails
# generation every time) can't make a single task run unbounded. Beat picks up
# the remainder on the next tick.
MAX_IMAGES_PER_RUN = 100


@shared_task(bind=True, ignore_result=True)
def backfill_missing_blurhashes_task(self, max_images: int = MAX_IMAGES_PER_RUN):
    """
    Generate blurhashes for PostImages that are missing one.

    Safety net for images whose blurhash failed to generate during image
    processing. It mirrors the generate_post_blurhashes management command but
    runs automatically on the Celery Beat schedule, so a transient failure no
    longer requires someone to run the command by hand.

    Args:
        max_images: Maximum number of images to process in a single run.

    Returns:
        Counts of processed/skipped/errored images for the sweep.
    """
    cutoff = timezone.now() - timedelta(minutes=BLURHASH_MIN_AGE_MINUTES)

    # Prefetch scaled variants so generate_blurhash_for_post_image can pick the
    # SMALL variant from the prefetch cache, avoiding a per-image query.
    images = list(
        PostImage.objects.filter(
            blurhash="",
            post__status=Post.Status.READY,
            post__created_at__lt=cutoff,
        )
        .prefetch_related("scaled_images")
        # Newest-first so the posts users are most likely to be viewing get a
        # placeholder first, and a chronically failing old image can't keep
        # starving newer ones out of the per-run limit.
        .order_by("-post__created_at", "order", "id")[:max_images]
    )

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for image in images:
        try:
            image_blurhash = generate_blurhash_for_post_image(image)
            if not image_blurhash:
                # generate_blurhash_for_post_image swallows its own errors and
                # returns None, so a permanently-failing image (e.g. a missing or
                # corrupt source file) stays blurhash="" and remains a candidate
                # on every run, re-downloading its source from storage each time.
                # Newest-first ordering keeps it from starving fresh posts, so the
                # wasted work is bounded, but there is no give-up mechanism: if this
                # ever shows up in the logs as a recurring skip, add a failure
                # counter / sentinel value so chronically bad images stop retrying.
                skipped_count += 1
                continue

            # Targeted update so we never touch other fields (e.g. processing_status)
            # that may have changed since the image was loaded.
            PostImage.objects.filter(pk=image.pk).update(blurhash=image_blurhash)
            processed_count += 1
        except Exception:
            error_count += 1
            logger.exception("Failed to backfill blurhash for PostImage %s", image.id)

    logger.info(
        "Blurhash backfill sweep: processed=%s skipped=%s errors=%s candidates=%s",
        processed_count,
        skipped_count,
        error_count,
        len(images),
    )
    return {
        "processed": processed_count,
        "skipped": skipped_count,
        "errors": error_count,
        "candidates": len(images),
    }

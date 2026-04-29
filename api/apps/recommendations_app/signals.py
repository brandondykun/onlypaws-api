"""
Signal receivers for the recommendations app.

PostInteraction is the sole signal source for short-term taste. When a new
PostInteraction row is created we drop two caches keyed by the interacting
profile:

    rec:short_term:{profile_id}    — so the next query embedding picks up the
                                     fresh signal.
    rec:batch:{profile_id}:0       — so the next pull-to-refresh produces a
    rec:batch_meta:{profile_id}:0    cache miss and regenerates batch 0 with
                                     the updated query embedding.

Mid-scroll batches (batch_id >= 1) are intentionally left intact so the
user's continuation pages don't shuffle under them.

VIEW interactions with sufficient dwell — and any high-intent interaction —
also re-stamp the post in the profile's seen sorted set so genuine views
persist longer through the rank-based cap than pagination-delivery entries.
"""

import logging
from types import SimpleNamespace

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.interactions_app.models import PostInteraction

from .batch import _batch_key, _batch_meta_key, record_seen_post_ids
from .services import (
    VIEW_DWELL_MIN_MS,
    interaction_count_cache_key,
    short_term_cache_key,
)

logger = logging.getLogger(__name__)


_HIGH_INTENT_TYPES = frozenset(
    (
        PostInteraction.InteractionType.LIKE,
        PostInteraction.InteractionType.SAVE,
        PostInteraction.InteractionType.COMMENT,
    )
)


@receiver(
    post_save, sender=PostInteraction, dispatch_uid="rec_invalidate_short_term_emb"
)
def invalidate_short_term_embedding_on_interaction(sender, instance, created, **kwargs):
    if not created:
        return

    profile_id = instance.profile_id
    cache.delete_many(
        [
            short_term_cache_key(profile_id),
            interaction_count_cache_key(profile_id),
            _batch_key(profile_id, 0),
            _batch_meta_key(profile_id, 0),
        ]
    )

    # Bump the seen-set score for genuine VIEWs (dwell ≥ MIN) and any
    # high-intent interaction. This re-stamps the post as "recently
    # confirmed seen" so it persists past the delivery-only TTL while
    # delivered-but-not-engaged posts still age out on schedule.
    is_engaging_view = (
        instance.interaction_type == PostInteraction.InteractionType.VIEW
        and instance.dwell_time_ms is not None
        and instance.dwell_time_ms >= VIEW_DWELL_MIN_MS
    )
    if is_engaging_view or instance.interaction_type in _HIGH_INTENT_TYPES:
        try:
            record_seen_post_ids(
                SimpleNamespace(id=profile_id), [instance.post_id]
            )
        except Exception:
            logger.warning(
                "rec seen-set bump failed for profile %s post %s",
                profile_id,
                instance.post_id,
                exc_info=True,
            )

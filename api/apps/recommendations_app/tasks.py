"""
Celery tasks for maintaining ProfilePreferenceEmbedding rows.

Three tasks:
- update_profile_preference_embedding_task: recompute one profile's embedding.
- update_stale_preference_embeddings_task: every 6h, queue refreshes for active
  profiles whose embedding is missing or stale.
- nightly_preference_embedding_refresh_task: safety net pass over profiles that
  interacted in the last 7 days.

Routing to the `recommendations` queue is configured in core/celery.py.
"""

import logging
from datetime import timedelta
from typing import Iterable

from celery import shared_task
from django.db.models import Exists, OuterRef
from django.utils import timezone

logger = logging.getLogger(__name__)


# Profiles are eligible for the 6-hourly sweep when their embedding is older
# than this OR missing entirely (and they have recent activity).
STALE_AFTER = timedelta(hours=6)
# Profiles must have at least one interaction in this window to be eligible
# for the routine 6-hourly sweep.
RECENT_ACTIVITY_WINDOW = timedelta(hours=24)
# Nightly safety-net window.
NIGHTLY_ACTIVITY_WINDOW = timedelta(days=7)
# Sweep dispatch tunables — avoid a single sweep enqueueing 100k tasks at once.
SWEEP_CHUNK_SIZE = 200
SWEEP_CHUNK_INTERVAL_SECONDS = 5
# Buffer past each task's ETA before it expires. `expires` is publish-time-relative,
# so it must include `countdown` to avoid dropping tasks at the tail of a large sweep.
SWEEP_TASK_EXPIRY_BUFFER_SECONDS = 3600


def _spread_sweep_dispatch(profile_ids: Iterable[int]) -> int:
    """Enqueue per-profile updates with a countdown spread across SWEEP_CHUNK_SIZE buckets.

    Accepts any iterable so callers can pass a streaming queryset (`.iterator()`)
    and avoid materializing every profile id in memory before enqueueing.

    With CHUNK_SIZE=200 and INTERVAL=5s, a 100k-profile sweep spreads across
    ~2500s (~42 min) instead of dumping 100k tasks into the broker at once.
    """
    queued = 0
    for index, profile_id in enumerate(profile_ids):
        bucket = index // SWEEP_CHUNK_SIZE
        countdown = bucket * SWEEP_CHUNK_INTERVAL_SECONDS
        update_profile_preference_embedding_task.apply_async(
            args=[profile_id],
            countdown=countdown,
            expires=countdown + SWEEP_TASK_EXPIRY_BUFFER_SECONDS,
        )
        queued += 1
    return queued


@shared_task(bind=True, max_retries=3)
def update_profile_preference_embedding_task(self, profile_id: int):
    """
    Recompute one profile's long-term preference embedding and persist it.

    Skips the persist step entirely when the new computation returns no signal
    AND a previously valid embedding exists, so a temporary signal drop never
    blanks a usable vector.
    """
    from apps.profile_app.models import Profile
    from apps.interactions_app.models import PostInteraction

    from .models import ProfilePreferenceEmbedding
    from .services import EMBEDDING_MODEL, compute_long_term_embedding

    try:
        try:
            profile = Profile.objects.get(id=profile_id)
        except Profile.DoesNotExist:
            logger.warning(
                f"Profile {profile_id} does not exist; skipping preference embedding update"
            )
            return {
                "success": False,
                "error": "profile_not_found",
                "profile_id": profile_id,
            }

        vec = compute_long_term_embedding(profile)
        existing = ProfilePreferenceEmbedding.objects.filter(profile=profile).first()

        if vec is None and existing is not None and existing.embedding is not None:
            logger.info(
                f"No fresh signal for profile {profile_id}; preserving existing embedding"
            )
            return {
                "success": True,
                "skipped": True,
                "reason": "no_signal_existing_preserved",
                "profile_id": profile_id,
            }

        interaction_count = PostInteraction.objects.filter(profile=profile).count()
        defaults = {
            "embedding": vec.tolist() if vec is not None else None,
            "last_computed_at": timezone.now(),
            "interaction_count_at_last_compute": interaction_count,
            "embedding_model": EMBEDDING_MODEL,
        }
        ProfilePreferenceEmbedding.objects.update_or_create(
            profile=profile, defaults=defaults
        )

        logger.info(
            f"Updated preference embedding for profile {profile_id} "
            f"(has_vec={vec is not None}, interactions={interaction_count})"
        )
        return {
            "success": True,
            "profile_id": profile_id,
            "has_embedding": vec is not None,
            "interaction_count": interaction_count,
        }

    except Exception as exc:
        logger.error(
            f"Error updating preference embedding for profile {profile_id}: {str(exc)}"
        )
        try:
            retry_delay = 30 * (2**self.request.retries)  # 30s, 60s, 120s
            raise self.retry(exc=exc, countdown=retry_delay)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded updating preference embedding for profile {profile_id}"
            )
            return {
                "success": False,
                "error": str(exc),
                "profile_id": profile_id,
                "retries": self.request.retries,
            }


@shared_task
def update_stale_preference_embeddings_task():
    """
    Queue update tasks for profiles whose embedding is missing or stale.

    Eligibility:
      - profile has at least one PostInteraction in the last 24 hours, AND
      - their preference_embedding row is missing OR last_computed_at < now - 6h.
    """
    from apps.interactions_app.models import PostInteraction

    now = timezone.now()
    activity_cutoff = now - RECENT_ACTIVITY_WINDOW
    stale_cutoff = now - STALE_AFTER

    from .models import ProfilePreferenceEmbedding

    active_profiles_qs = (
        PostInteraction.objects.filter(created_at__gte=activity_cutoff)
        .values_list("profile_id", flat=True)
        .distinct()
    )

    fresh_embeddings = ProfilePreferenceEmbedding.objects.filter(
        profile_id=OuterRef("profile_id"),
        last_computed_at__gte=stale_cutoff,
    )
    pending_qs = (
        PostInteraction.objects.filter(created_at__gte=activity_cutoff)
        .annotate(has_fresh=Exists(fresh_embeddings))
        .filter(has_fresh=False)
        .values_list("profile_id", flat=True)
        .distinct()
    )

    active_count = active_profiles_qs.count()
    queued = _spread_sweep_dispatch(pending_qs.iterator(chunk_size=1000))
    skipped = active_count - queued

    logger.info(
        f"Stale preference-embedding sweep: queued={queued} skipped={skipped} "
        f"active_profiles={active_count}"
    )
    return {"queued": queued, "skipped": skipped}


@shared_task
def refresh_popularity_cache_task():
    """
    Recompute the popularity sorted set in Redis used as the cold-start
    fallback. Runs every 30 minutes.
    """
    from .popularity import refresh_popularity_set

    written = refresh_popularity_set()
    return {"written": written}


@shared_task
def refresh_heavily_reported_profiles_task():
    """
    Recompute the set of profile IDs with >=5 open reports and write it to
    cache for explore-feed filtering. Runs every 5 minutes so readers never
    pay the aggregation cost on the request path.
    """
    from django.core.cache import cache
    from django.db.models import Count, Q

    from apps.profile_app.models import Profile

    from .batch import HEAVY_REPORTED_CACHE_KEY, HEAVY_REPORTED_CACHE_TTL

    ids = list(
        Profile.objects.annotate(
            _arc=Count(
                "profile_reports",
                filter=Q(profile_reports__status__in=["PENDING", "UNDER_REVIEW"]),
            )
        )
        .filter(_arc__gte=5)
        .values_list("id", flat=True)
    )
    cache.set(HEAVY_REPORTED_CACHE_KEY, ids, timeout=HEAVY_REPORTED_CACHE_TTL)
    logger.info(f"Refreshed heavily-reported profile cache: count={len(ids)}")
    return {"count": len(ids)}


@shared_task
def nightly_preference_embedding_refresh_task():
    """
    Safety net: queue refreshes for every profile that interacted in the past 7 days.
    """
    from apps.interactions_app.models import PostInteraction

    cutoff = timezone.now() - NIGHTLY_ACTIVITY_WINDOW
    profile_ids_qs = (
        PostInteraction.objects.filter(created_at__gte=cutoff)
        .values_list("profile_id", flat=True)
        .distinct()
    )

    queued = _spread_sweep_dispatch(profile_ids_qs.iterator(chunk_size=1000))

    logger.info(f"Nightly preference-embedding refresh: queued={queued}")
    return {"queued": queued}

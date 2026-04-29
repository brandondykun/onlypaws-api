"""
Popularity-based fallback feed.

Used for cold-start users (no preference embedding yet) and as a final safety
net when the preference-based feed would otherwise be empty. A Celery beat task
recomputes a Redis sorted set of the top ~2000 posts every 30 minutes; the
fallback reader filters that set down to a hash-shuffled per-profile slice.
"""

from __future__ import annotations

import hashlib
import logging
import math
import random
from datetime import timedelta
from typing import Iterable

import redis
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from .queryset_utils import recommendable_posts_qs

logger = logging.getLogger(__name__)


POPULARITY_KEY = "rec:popular_posts:7d"
POPULARITY_SET_SIZE = 2000
POPULARITY_LOOKBACK = timedelta(days=7)
# Heavily-reported profiles are filtered using the same threshold the explore
# view uses today.
HEAVY_REPORT_THRESHOLD = 5


_redis_singleton: redis.Redis | None = None


def _redis_client() -> redis.Redis:
    """Dedicated redis-py client for sorted-set operations the cache API can't express."""
    global _redis_singleton
    if _redis_singleton is None:
        _redis_singleton = redis.Redis.from_url(
            settings.CACHES["default"]["LOCATION"],
            decode_responses=False,
        )
    return _redis_singleton


def _engagement_score(
    likes: int, saves: int, comments: int, views: int, age_hours: float
) -> float:
    """Weighted engagement / age^1.5. Saves and comments matter more than likes/views."""
    raw = likes + 3.0 * saves + 2.5 * comments + 0.5 * views
    if raw <= 0:
        return 0.0
    # Floor age at 1 hour so brand-new posts don't divide-by-near-zero.
    safe_age = max(age_hours, 1.0)
    return raw / math.pow(safe_age, 1.5)


def refresh_popularity_set() -> int:
    """
    Recompute the popularity sorted set in Redis. Returns the number of posts
    written. Atomically replaces the existing set via DEL + ZADD in a pipeline.
    """
    from apps.profile_app.models import Profile

    now = timezone.now()
    cutoff = now - POPULARITY_LOOKBACK

    heavily_reported_profile_ids = (
        Profile.objects.annotate(
            _arc=Count(
                "profile_reports",
                filter=Q(profile_reports__status__in=["PENDING", "UNDER_REVIEW"]),
            )
        )
        .filter(_arc__gte=HEAVY_REPORT_THRESHOLD)
        .values_list("id", flat=True)
    )

    qs = (
        recommendable_posts_qs()
        .filter(created_at__gte=cutoff)
        .exclude(profile_id__in=heavily_reported_profile_ids)
        .annotate(
            _likes=Count("likes", distinct=True),
            _saves=Count("saved_by", distinct=True),
            _comments=Count("comments", distinct=True),
            _views=Count(
                "interactions",
                filter=Q(interactions__interaction_type="view"),
                distinct=True,
            ),
        )
        .values("id", "created_at", "_likes", "_saves", "_comments", "_views")
    )

    scored: list[tuple[int, float]] = []
    for row in qs.iterator(chunk_size=1000):
        age_hours = (now - row["created_at"]).total_seconds() / 3600.0
        score = _engagement_score(
            row["_likes"], row["_saves"], row["_comments"], row["_views"], age_hours
        )
        if score > 0.0:
            scored.append((row["id"], score))

    scored.sort(key=lambda t: t[1], reverse=True)
    top = scored[:POPULARITY_SET_SIZE]

    client = _redis_client()
    if top:
        # Build the new set under a temp key, then RENAME atomically over the
        # live key. RENAME is a single operation, so concurrent readers either
        # see the old set or the new set — never the empty interval that DEL
        # + ZADD would expose.
        staging_key = f"{POPULARITY_KEY}:staging"
        pipe = client.pipeline(transaction=True)
        pipe.delete(staging_key)
        pipe.zadd(staging_key, {post_id: score for post_id, score in top})
        pipe.rename(staging_key, POPULARITY_KEY)
        pipe.execute()
    else:
        # Nothing to write — leave the existing set in place rather than
        # blanking it. Empty popularity is a degraded state we'd rather not
        # ship to readers.
        logger.warning("Popularity refresh produced 0 candidates; skipping write")

    logger.info(
        f"Refreshed popularity set: candidates_scored={len(scored)} written={len(top)}"
    )
    return len(top)


def _seeded_shuffle(
    ids: list[int],
    profile_id: int,
    batch_id: int,
    shuffle_token: int | None = None,
) -> list[int]:
    """Deterministic per-(profile, batch) shuffle so refreshes are stable within a session."""
    digest = hashlib.sha1(
        f"{profile_id}:{batch_id}:{shuffle_token or 0}".encode("utf-8")
    ).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = random.Random(seed)
    shuffled = list(ids)
    rng.shuffle(shuffled)
    return shuffled


def get_popularity_fallback_ids(
    profile,
    batch_size: int,
    exclude_post_ids: Iterable[int],
    blocked_ids: Iterable[int],
    batch_id: int = 0,
    allow_seen_backfill: bool = False,
    shuffle_token: int | None = None,
    excluded_profile_ids: Iterable[int] | None = None,
) -> list[int]:
    """
    Return up to `batch_size` post IDs for a cold-start user.

    Steps:
      1. Pull a generous slice (3x the requested batch) of top-popularity post IDs.
      2. Drop blocked-profile and self-authored posts.
      3. Prefer unseen posts, backfilling seen posts only when requested.
      4. Hash-shuffle deterministically by (profile_id, batch_id, shuffle_token).
      5. If Redis is empty (e.g. fresh deploy), fall back to recency.

    `excluded_profile_ids` lets callers (e.g. the personalised vector path
    topping up an underfilled batch) reuse the same broad exclusion set
    (own + followed + blocked + heavily-reported) the vector path applied,
    so the popularity backfill doesn't reintroduce content the vector path
    would have rejected.
    """
    exclude_set = set(exclude_post_ids)
    blocked_set = set(blocked_ids)
    excluded_profile_set = (
        set(excluded_profile_ids) if excluded_profile_ids is not None else set()
    )

    client = _redis_client()
    raw = client.zrevrange(POPULARITY_KEY, 0, batch_size * 3 - 1)
    candidate_ids = [int(member) for member in raw]

    if not candidate_ids:
        logger.info("Popularity Redis set empty; falling back to recency.")
        recency_exclude = set() if allow_seen_backfill else exclude_set
        candidate_ids = _recency_fallback_ids(
            profile,
            batch_size * 3,
            recency_exclude,
            blocked_set,
            excluded_profile_ids=excluded_profile_set,
        )
        if not candidate_ids:
            return []

    # Single round-trip to confirm profile_id, ensure the post still exists, and
    # re-apply the recommendable filter. The popularity Redis set is refreshed
    # on a 30-min cadence, so a post reported as inappropriate between refreshes
    # would otherwise leak through until the next refresh lands.
    rows = (
        recommendable_posts_qs()
        .filter(id__in=candidate_ids)
        .exclude(profile__user=profile.user)
        .exclude(profile_id__in=blocked_set)
        .exclude(profile_id__in=excluded_profile_set)
        .values_list("id", "profile_id")
    )
    valid_ids = {row[0]: row[1] for row in rows}

    valid_candidate_ids = [pid for pid in candidate_ids if pid in valid_ids]
    unseen_ids = [pid for pid in valid_candidate_ids if pid not in exclude_set]
    unseen_shuffled = _seeded_shuffle(
        unseen_ids,
        profile.id,
        batch_id,
        shuffle_token=shuffle_token,
    )

    if not allow_seen_backfill:
        return unseen_shuffled[:batch_size]

    seen_ids = [pid for pid in valid_candidate_ids if pid in exclude_set]
    seen_shuffled = _seeded_shuffle(
        seen_ids,
        profile.id,
        batch_id,
        shuffle_token=shuffle_token,
    )
    return (unseen_shuffled + seen_shuffled)[:batch_size]


def _recency_fallback_ids(
    profile,
    limit: int,
    exclude_set: set,
    blocked_set: set,
    excluded_profile_ids: set | None = None,
) -> list[int]:
    """Last-resort recency feed for a fresh deploy where Redis is empty."""
    qs = (
        recommendable_posts_qs()
        .exclude(profile__user=profile.user)
        .exclude(profile_id__in=blocked_set)
        .exclude(id__in=exclude_set)
    )
    if excluded_profile_ids:
        qs = qs.exclude(profile_id__in=excluded_profile_ids)
    return list(qs.order_by("-created_at").values_list("id", flat=True)[:limit])

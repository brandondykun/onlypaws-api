"""
Explore-feed batch generation.

A "batch" is a list of up to BATCH_SIZE post IDs personalised for one profile,
materialised in Redis so that infinite scroll within the same batch is cheap
(one pgvector + filter pass per BATCH_SIZE pages, not per page).

Public entry points:
    get_or_create_batch(profile, batch_id) -> (post_ids, source)
    get_seen_post_ids(profile) -> list[int]
    record_seen_post_ids(profile, post_ids)
"""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.interactions_app.models import Follow
from apps.moderation_app.block_utils import get_blocked_profile_ids
from apps.posts_app.models import Post
from apps.profile_app.models import Profile

from .popularity import get_popularity_fallback_ids
from .queryset_utils import recommendable_posts_qs
from .services import EMBEDDING_DIM, EMBEDDING_MODEL, get_query_embedding

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #

BATCH_SIZE = 300
PAGE_SIZE = 24
MAX_PER_PROFILE = 5
CANDIDATE_PULL_MULTIPLIER = 2  # pull 600, return 300
EF_SEARCH = 200  # pgvector HNSW ef_search override for the recommendation query
MMR_LAMBDA = 0.3

BATCH_TTL_SECONDS = 1800  # 30 min
SEEN_TTL_SECONDS = 21600  # 6 h — delivery-only entries age out quickly
SEEN_CAP = 5000  # most-recent seen IDs retained per profile
SEEN_SQL_EXCLUDE_CAP = 2000  # most-recent seen IDs passed into SQL NOT IN clause

HEAVY_REPORTED_CACHE_KEY = "rec:heavily_reported_profile_ids"
HEAVY_REPORTED_CACHE_TTL = 1800  # 30 min safety net; refresher beat task runs every 5 min


def _batch_key(profile_id: int, batch_id: int) -> str:
    return f"rec:batch:{profile_id}:{batch_id}"


def _batch_meta_key(profile_id: int, batch_id: int) -> str:
    return f"rec:batch_meta:{profile_id}:{batch_id}"


def _seen_key(profile_id: int) -> str:
    return f"rec:seen:{profile_id}"


def _refresh_generation_key(profile_id: int) -> str:
    return f"rec:refresh_generation:{profile_id}"


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


# --------------------------------------------------------------------------- #
# Seen-ID tracking
# --------------------------------------------------------------------------- #


def get_seen_post_ids(profile, limit: int = SEEN_SQL_EXCLUDE_CAP) -> list[int]:
    """Return the most-recent `limit` seen post IDs for the profile.

    Members older than SEEN_TTL_SECONDS are pruned by score before reading
    so delivered-but-not-viewed posts age out without lingering in the set.
    """
    client = _redis_client()
    key = _seen_key(profile.id)
    cutoff = timezone.now().timestamp() - SEEN_TTL_SECONDS
    pipe = client.pipeline()
    pipe.zremrangebyscore(key, "-inf", cutoff)
    # ZREVRANGE is by index; we want the highest-score (most-recent) members first.
    pipe.zrevrange(key, 0, limit - 1)
    _, raw = pipe.execute()
    return [int(member) for member in raw]


def record_seen_post_ids(profile, post_ids: Iterable[int]) -> None:
    """Append IDs to the seen sorted set with score=now; trim to SEEN_CAP.

    Called on both pagination delivery and on confirmed PostInteraction VIEW
    events. Re-stamping a post's score on a real view bumps it back to the
    top of the cap, so genuinely-viewed posts persist longer than ones the
    client merely prefetched.
    """
    ids = list(post_ids)
    if not ids:
        return
    now = timezone.now().timestamp()
    key = _seen_key(profile.id)

    client = _redis_client()
    pipe = client.pipeline()
    pipe.zadd(key, {pid: now for pid in ids})
    # Keep only the most-recent SEEN_CAP entries (drop oldest by score ascending).
    pipe.zremrangebyrank(key, 0, -SEEN_CAP - 1)
    pipe.expire(key, SEEN_TTL_SECONDS)
    pipe.execute()


# --------------------------------------------------------------------------- #
# Per-profile cap + MMR re-rank
# --------------------------------------------------------------------------- #


def _cap_per_profile(
    candidates: list[tuple[int, int, list]],
    max_per_profile: int = MAX_PER_PROFILE,
) -> list[tuple[int, int, list]]:
    """Walk candidates in order, dropping any beyond max_per_profile per profile."""
    counts: dict[int, int] = {}
    out = []
    for cid, pid, emb in candidates:
        if counts.get(pid, 0) >= max_per_profile:
            continue
        out.append((cid, pid, emb))
        counts[pid] = counts.get(pid, 0) + 1
    return out


def _mmr_select(
    candidates: list[tuple[int, int, list]],
    query: np.ndarray,
    target_size: int,
    lambda_param: float = MMR_LAMBDA,
) -> list[int]:
    """
    Greedy MMR re-rank. Returns up to `target_size` post IDs in selection order.

    Score for an unselected candidate c is:
        sim(q, c) - lambda * max_{s in selected} sim(c, s)

    Vectorised for speed.
    """
    if not candidates:
        return []

    n = len(candidates)
    target = min(target_size, n)

    emb_matrix = np.asarray([c[2] for c in candidates], dtype=np.float64)
    norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    emb_norm = emb_matrix / norms

    q = np.asarray(query, dtype=np.float64)
    q_norm_val = np.linalg.norm(q)
    if q_norm_val == 0.0:
        # Without a query direction, fall back to the SQL ordering.
        return [c[0] for c in candidates[:target]]
    q_unit = q / q_norm_val

    sims_to_query = emb_norm @ q_unit  # (n,)
    max_sim_to_selected = np.zeros(n, dtype=np.float64)

    selected_indices: list[int] = []
    selected_mask = np.zeros(n, dtype=bool)

    # First pick: highest similarity to query.
    first = int(np.argmax(sims_to_query))
    selected_indices.append(first)
    selected_mask[first] = True
    max_sim_to_selected = np.maximum(max_sim_to_selected, emb_norm @ emb_norm[first])

    while len(selected_indices) < target:
        scores = sims_to_query - lambda_param * max_sim_to_selected
        scores[selected_mask] = -np.inf
        next_idx = int(np.argmax(scores))
        if not np.isfinite(scores[next_idx]):
            break
        selected_indices.append(next_idx)
        selected_mask[next_idx] = True
        max_sim_to_selected = np.maximum(
            max_sim_to_selected, emb_norm @ emb_norm[next_idx]
        )

    return [candidates[i][0] for i in selected_indices]


# --------------------------------------------------------------------------- #
# Batch generation
# --------------------------------------------------------------------------- #


def _heavily_reported_profile_ids() -> list[int]:
    # Populated by refresh_heavily_reported_profiles_task. Fail open with [] so a
    # cold cache (fresh deploy, beat outage) doesn't synchronously run the
    # Profile aggregation on the request path and stampede on TTL expiry.
    return cache.get(HEAVY_REPORTED_CACHE_KEY) or []


def _own_profile_ids(profile) -> list[int]:
    """All profile IDs owned by the same user, so we never recommend self-authored posts."""
    return list(
        Profile.objects.filter(user_id=profile.user_id).values_list("id", flat=True)
    )


def _followed_profile_ids(profile) -> list[int]:
    return list(
        Follow.objects.filter(followed_by_id=profile.id).values_list(
            "followed_id", flat=True
        )
    )


def _next_refresh_generation(profile) -> int:
    """Monotonic per-profile token used to vary regenerated first batches.

    Uses the raw redis client's INCR (atomic, creates the key on first call)
    rather than cache.add+cache.incr, which races on eviction and is non-atomic
    in Django's built-in RedisCache.
    """
    key = _refresh_generation_key(profile.id)
    client = _redis_client()
    try:
        generation = client.incr(key)
        client.expire(key, SEEN_TTL_SECONDS)
        return int(generation)
    except Exception:
        # Refresh-generation is a best-effort shuffle token; on Redis failure
        # we'd rather render the feed than 500 the request.
        logger.warning("refresh_generation incr failed", exc_info=True)
        return 0


def _should_regenerate_first_batch(
    profile, cached_ids: list[int], refresh: bool
) -> bool:
    if not refresh or not cached_ids:
        return False

    first_page = cached_ids[:PAGE_SIZE]
    seen_ids = set(get_seen_post_ids(profile, limit=PAGE_SIZE * 2))
    return bool(first_page) and set(first_page).issubset(seen_ids)


def _fetch_embedding_candidates(
    profile,
    query_emb: np.ndarray,
    excluded_profile_ids: Iterable[int],
    exclude_post_ids: Iterable[int],
    pull_size: int,
) -> list[tuple[int, int, list]]:
    sql_exclude = list(exclude_post_ids)
    if len(sql_exclude) > SEEN_SQL_EXCLUDE_CAP:
        sql_exclude = sql_exclude[:SEEN_SQL_EXCLUDE_CAP]

    with transaction.atomic():
        # Widen HNSW recall for this query only. SET LOCAL is scoped to the
        # transaction, so it does not leak to other connections.
        with connection.cursor() as cur:
            cur.execute("SET LOCAL hnsw.ef_search = %s", [EF_SEARCH])

        candidates_qs = (
            recommendable_posts_qs()
            .filter(
                combined_embedding__isnull=False,
                combined_embedding_model=EMBEDDING_MODEL,
            )
            .exclude(profile_id__in=excluded_profile_ids)
            .exclude(id__in=sql_exclude)
            .annotate(distance=CosineDistance("combined_embedding", query_emb.tolist()))
            .order_by("distance")
            .values_list("id", "profile_id", "combined_embedding")[:pull_size]
        )
        return list(candidates_qs)


def _select_with_seen_backfill(
    candidates: list[tuple[int, int, list]],
    query_emb: np.ndarray,
    target_size: int,
    seen_ids: set[int],
) -> list[int]:
    unseen_candidates = [
        candidate for candidate in candidates if candidate[0] not in seen_ids
    ]
    seen_candidates = [
        candidate for candidate in candidates if candidate[0] in seen_ids
    ]

    capped_unseen = _cap_per_profile(unseen_candidates, MAX_PER_PROFILE)
    selected = _mmr_select(capped_unseen, query_emb, target_size, MMR_LAMBDA)

    remaining = target_size - len(selected)
    if remaining <= 0:
        return selected

    selected_set = set(selected)
    seen_backfill = [
        candidate for candidate in seen_candidates if candidate[0] not in selected_set
    ]
    capped_seen = _cap_per_profile(seen_backfill, MAX_PER_PROFILE)
    selected.extend(_mmr_select(capped_seen, query_emb, remaining, MMR_LAMBDA))
    return selected


def generate_explore_batch(
    profile,
    batch_id: int,
    exclude_post_ids: Iterable[int],
    allow_seen_backfill: bool = False,
    refresh_generation: int | None = None,
) -> tuple[list[int], str]:
    """
    Build a fresh batch of up to BATCH_SIZE post IDs for the given profile.

    Returns (post_ids, source) where source ∈ {"long+short", "long_only",
    "short_only", "popularity", "long+short+popularity", "long_only+popularity",
    "short_only+popularity"}. The "+popularity" suffix marks batches whose
    vector path was underfilled and were topped up from the popularity feed.
    """
    query_emb, source = get_query_embedding(profile)
    blocked_ids = get_blocked_profile_ids(profile)
    exclude_set = set(exclude_post_ids)

    if query_emb is None:
        ids = get_popularity_fallback_ids(
            profile=profile,
            batch_size=BATCH_SIZE,
            exclude_post_ids=exclude_set,
            blocked_ids=blocked_ids,
            batch_id=batch_id,
            allow_seen_backfill=allow_seen_backfill,
            shuffle_token=refresh_generation,
        )
        logger.info(
            f"explore batch profile={profile.id} batch_id={batch_id} "
            f"source=popularity size={len(ids)}"
        )
        return ids, "popularity"

    excluded_profile_ids = (
        set(_own_profile_ids(profile))
        | set(_followed_profile_ids(profile))
        | set(blocked_ids)
        | set(_heavily_reported_profile_ids())
    )
    pull_size = BATCH_SIZE * CANDIDATE_PULL_MULTIPLIER
    hard_exclude = exclude_set if not allow_seen_backfill else set()
    candidates = _fetch_embedding_candidates(
        profile,
        query_emb,
        excluded_profile_ids,
        hard_exclude,
        pull_size,
    )

    if not candidates:
        selected: list[int] = []
        capped_count = 0
    elif allow_seen_backfill:
        selected = _select_with_seen_backfill(
            candidates, query_emb, BATCH_SIZE, exclude_set
        )
        capped_count = len(candidates)
    else:
        capped = _cap_per_profile(candidates, MAX_PER_PROFILE)
        selected = _mmr_select(capped, query_emb, BATCH_SIZE, MMR_LAMBDA)
        capped_count = len(capped)

    # Top up with popularity when the vector path is short. Without this a
    # heavy follow list, large seen set, or sparse-niche embedding can produce
    # an empty or underfilled batch and dead-end infinite scroll. The topup
    # reuses the vector path's broader exclusion set so it doesn't reintroduce
    # content the vector path filtered out (followed, heavily-reported, etc.).
    topup_count = 0
    if len(selected) < BATCH_SIZE:
        deficit = BATCH_SIZE - len(selected)
        selected_set = set(selected)
        topup_ids = get_popularity_fallback_ids(
            profile=profile,
            batch_size=deficit,
            exclude_post_ids=exclude_set | selected_set,
            blocked_ids=blocked_ids,
            batch_id=batch_id,
            allow_seen_backfill=allow_seen_backfill,
            shuffle_token=refresh_generation,
            excluded_profile_ids=excluded_profile_ids,
        )
        if topup_ids:
            new_ids = [pid for pid in topup_ids if pid not in selected_set]
            selected = list(selected) + new_ids
            topup_count = len(new_ids)
            source = "popularity" if not candidates else f"{source}+popularity"

    logger.info(
        f"explore batch profile={profile.id} batch_id={batch_id} source={source} "
        f"pulled={len(candidates)} capped={capped_count} "
        f"selected={len(selected)} topup={topup_count}"
    )
    return selected, source


def get_or_create_batch(
    profile,
    batch_id: int,
    refresh: bool = False,
) -> tuple[list[int], str]:
    """
    Return (post_ids, source) for the requested batch, regenerating only on
    cache miss.

    Seen-ID exclusion behavior:
      - batch_id == 0 is generated WITHOUT honoring the seen-ID set on first
        load so the user always gets a populated top-of-feed.
      - cursorless refreshes for batch_id == 0 regenerate once the cached first
        page has already been seen. They prefer unseen posts, but backfill from
        seen posts when inventory is too small.
      - batch_id >= 1 (mid-scroll continuation batches) DO exclude
        previously-seen posts so continuous scrolling surfaces fresh content.
    """
    cached_ids = cache.get(_batch_key(profile.id, batch_id))
    if cached_ids is not None:
        cached_ids = list(cached_ids)
        if not (
            batch_id == 0
            and _should_regenerate_first_batch(profile, cached_ids, refresh)
        ):
            meta = cache.get(_batch_meta_key(profile.id, batch_id)) or "unknown"
            return cached_ids, meta

    refresh_first_batch = refresh and batch_id == 0
    seen = get_seen_post_ids(profile) if batch_id > 0 or refresh_first_batch else []
    refresh_generation = (
        _next_refresh_generation(profile) if refresh_first_batch and seen else None
    )
    ids, source = generate_explore_batch(
        profile,
        batch_id,
        seen,
        allow_seen_backfill=refresh_first_batch,
        refresh_generation=refresh_generation,
    )

    cache.set(_batch_key(profile.id, batch_id), ids, timeout=BATCH_TTL_SECONDS)
    cache.set(_batch_meta_key(profile.id, batch_id), source, timeout=BATCH_TTL_SECONDS)
    return ids, source

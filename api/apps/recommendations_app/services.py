"""
Recommendation embedding service.

Stateless functions that derive personalised embeddings from a profile's
PostInteraction history. Long-term embeddings are persisted on
ProfilePreferenceEmbedding; short-term embeddings are computed per-request and
cached briefly in Redis. The two are blended into a query vector used to search
the Post combined_embedding HNSW index.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional, Tuple

import numpy as np
from django.core.cache import cache
from django.utils import timezone

from apps.interactions_app.models import PostInteraction
from apps.posts_app.models import Post

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tunable constants
# --------------------------------------------------------------------------- #

EMBEDDING_DIM = 512
EMBEDDING_MODEL = "sentence-transformers/clip-ViT-B-32"

TYPE_WEIGHTS = {
    PostInteraction.InteractionType.SAVE: 5.0,
    PostInteraction.InteractionType.LIKE: 3.0,
    PostInteraction.InteractionType.COMMENT: 2.5,
    PostInteraction.InteractionType.VIEW: 1.0,
    PostInteraction.InteractionType.PREVIEW_CLICK: 0.3,
}

# A view shorter than this is treated as a bounce and contributes no signal.
VIEW_DWELL_MIN_MS = 1500
# Each extra 5 seconds of dwell adds 1.0 to the view multiplier, capped at 3x.
VIEW_DWELL_DIVISOR_MS = 5000.0
VIEW_DWELL_MAX_MULTIPLIER = 3.0

LONG_TERM_LOOKBACK_DAYS = 30  # capped by PostInteraction retention policy
LONG_TERM_MAX_EVENTS = 500
LONG_TERM_HALF_LIFE_DAYS = 30

SHORT_TERM_LOOKBACK_HOURS = 24
SHORT_TERM_MAX_EVENTS = 50
SHORT_TERM_HALF_LIFE_HOURS = 12
SHORT_TERM_CACHE_TTL = 300  # seconds
INTERACTION_COUNT_CACHE_TTL = 300  # seconds — gates α (coarse 3-bucket selector)

# Persisted long-term embeddings need stronger signal than per-request
# short-term intent, which should react quickly to a recent like or long dwell.
MIN_WEIGHTED_SIGNAL = 5.0
SHORT_TERM_MIN_WEIGHTED_SIGNAL = 2.5
WEIGHTED_SIGNAL_EPSILON = 1e-4

# α thresholds: (interaction_count_upper_bound, alpha). Sorted ascending.
ALPHA_THRESHOLDS = [(50, 0.25), (200, 0.45)]
ALPHA_DEFAULT = 0.65


def short_term_cache_key(profile_id: int) -> str:
    return f"rec:short_term:{profile_id}"


def interaction_count_cache_key(profile_id: int) -> str:
    return f"rec:int_count:{profile_id}"


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _weight_for(
    interaction_type: str,
    dwell_ms: Optional[int],
    age_seconds: float,
    half_life_seconds: float,
) -> float:
    base = TYPE_WEIGHTS.get(interaction_type, 0.0)
    if base == 0.0:
        return 0.0

    if interaction_type == PostInteraction.InteractionType.VIEW:
        if dwell_ms is None or dwell_ms < VIEW_DWELL_MIN_MS:
            return 0.0
        multiplier = min(
            1.0 + (dwell_ms / VIEW_DWELL_DIVISOR_MS),
            VIEW_DWELL_MAX_MULTIPLIER,
        )
        base *= multiplier

    decay = 0.5 ** (max(age_seconds, 0.0) / half_life_seconds)
    return base * decay


def _compute_weighted_average(
    profile,
    lookback_seconds: float,
    max_events: int,
    half_life_seconds: float,
    min_weighted_signal: float = MIN_WEIGHTED_SIGNAL,
) -> Optional[np.ndarray]:
    """
    Aggregate the profile's recent interactions into a single L2-normalized
    embedding. Returns None when total weighted signal is too weak to trust.
    """
    cutoff = timezone.now() - timedelta(seconds=lookback_seconds)

    interactions = list(
        PostInteraction.objects.filter(
            profile=profile,
            created_at__gte=cutoff,
            post__combined_embedding__isnull=False,
            post__status=Post.Status.READY,
            post__combined_embedding_model=EMBEDDING_MODEL,
        )
        .order_by("-created_at")
        .values("post_id", "interaction_type", "dwell_time_ms", "created_at")[
            :max_events
        ]
    )

    if not interactions:
        return None

    unique_post_ids = {row["post_id"] for row in interactions}
    embeddings_by_post = dict(
        Post.objects.filter(
            id__in=unique_post_ids, combined_embedding__isnull=False
        ).values_list("id", "combined_embedding")
    )

    now = timezone.now()
    weighted_sum = np.zeros(EMBEDDING_DIM, dtype=np.float64)
    total_weight = 0.0

    for row in interactions:
        embedding = embeddings_by_post.get(row["post_id"])
        if embedding is None:
            continue
        age_seconds = (now - row["created_at"]).total_seconds()
        weight = _weight_for(
            row["interaction_type"],
            row["dwell_time_ms"],
            age_seconds,
            half_life_seconds,
        )
        if weight <= 0.0:
            continue
        weighted_sum += np.asarray(embedding, dtype=np.float64) * weight
        total_weight += weight

    if total_weight + WEIGHTED_SIGNAL_EPSILON < min_weighted_signal:
        return None

    avg = weighted_sum / total_weight
    norm = np.linalg.norm(avg)
    if norm == 0.0:
        return None
    return avg / norm


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def compute_long_term_embedding(profile) -> Optional[np.ndarray]:
    """Weighted average of the profile's last 30 days of interactions."""
    return _compute_weighted_average(
        profile,
        lookback_seconds=LONG_TERM_LOOKBACK_DAYS * 86400,
        max_events=LONG_TERM_MAX_EVENTS,
        half_life_seconds=LONG_TERM_HALF_LIFE_DAYS * 86400,
    )


def compute_short_term_embedding(profile) -> Optional[np.ndarray]:
    """
    Weighted average of the profile's last 24 hours of interactions, cached
    for SHORT_TERM_CACHE_TTL seconds. Cache is invalidated on PostInteraction
    creation by a signal in apps.recommendations_app.signals.
    """
    cache_key = short_term_cache_key(profile.id)
    cached = cache.get(cache_key)
    if cached is not None:
        # Sentinel for cached "no signal" so we don't recompute on every miss.
        if cached == "none":
            return None
        return np.asarray(cached, dtype=np.float64)

    vec = _compute_weighted_average(
        profile,
        lookback_seconds=SHORT_TERM_LOOKBACK_HOURS * 3600,
        max_events=SHORT_TERM_MAX_EVENTS,
        half_life_seconds=SHORT_TERM_HALF_LIFE_HOURS * 3600,
        min_weighted_signal=SHORT_TERM_MIN_WEIGHTED_SIGNAL,
    )
    cache.set(
        cache_key,
        vec.tolist() if vec is not None else "none",
        timeout=SHORT_TERM_CACHE_TTL,
    )
    return vec


def _alpha_for(interaction_count: int) -> float:
    """Adaptive blend weight: new accounts lean short-term, mature accounts long-term."""
    for upper, alpha in ALPHA_THRESHOLDS:
        if interaction_count < upper:
            return alpha
    return ALPHA_DEFAULT


def _recent_interaction_count(profile) -> int:
    """Live, briefly-cached count of the profile's PostInteractions.

    Gates α so blend weighting reflects current engagement maturity rather
    than the snapshot frozen at last embedding compute (which only updates
    when the long-term embedding is persisted, possibly hours behind reality).
    Mirrors the count shape used by update_profile_preference_embedding_task
    so α bucket calibration stays consistent.
    """
    cache_key = interaction_count_cache_key(profile.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    count = PostInteraction.objects.filter(profile=profile).count()
    cache.set(cache_key, count, timeout=INTERACTION_COUNT_CACHE_TTL)
    return count


def _load_long_term(profile) -> Optional[np.ndarray]:
    pref = getattr(profile, "preference_embedding", None)
    if pref is None or pref.embedding is None:
        return None
    if pref.embedding_model != EMBEDDING_MODEL:
        # Embedding was generated against a different model; skip until the
        # next recompute lands.
        logger.info(
            f"Skipping long-term embedding for profile {profile.id}: "
            f"model mismatch ({pref.embedding_model} vs {EMBEDDING_MODEL})"
        )
        return None
    return np.asarray(pref.embedding, dtype=np.float64)


def get_query_embedding(profile) -> Tuple[Optional[np.ndarray], str]:
    """
    Build the query vector for an explore search.

    Returns (vec, source). source ∈ {"long+short", "long_only", "short_only",
    "cold"}. "cold" means no usable signal — caller should fall back to a
    popularity-based feed.
    """
    long_vec = _load_long_term(profile)
    short_vec = compute_short_term_embedding(profile)

    if long_vec is None and short_vec is None:
        return None, "cold"
    if long_vec is None:
        return short_vec, "short_only"
    if short_vec is None:
        return long_vec, "long_only"

    alpha = _alpha_for(_recent_interaction_count(profile))
    combined = alpha * long_vec + (1.0 - alpha) * short_vec
    norm = np.linalg.norm(combined)
    if norm == 0.0:
        return None, "cold"
    return combined / norm, "long+short"

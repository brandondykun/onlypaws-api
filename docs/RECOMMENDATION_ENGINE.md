# Recommendation Engine

This document explains how the Only Paws recommendation engine powers the personalized Explore feed, how data moves through the system, and how to debug common issues.

## Overview

The recommendation engine lives mainly in `api/apps/recommendations_app/` and is integrated into the Explore endpoint in `api/apps/posts_app/views.py`.

At a high level, the engine:

1. Records profile interactions with posts.
2. Converts those interactions into profile taste embeddings.
3. Uses the profile embedding to search for similar post embeddings with pgvector.
4. Filters unsafe or ineligible posts.
5. Diversifies the result set.
6. Caches batches of recommended post IDs in Redis.
7. Falls back to popularity or recency when personalization is not possible.

The key mental model is:

> Explore does not rank one page at a time. It builds a Redis-backed batch of up to 300 recommended post IDs, then cursor pagination slices 24 IDs at a time from that batch.

## Conceptual Model

A few non-obvious properties of how the engine represents user taste. These shape what the system can and cannot do.

### Taste is a single point in vector space

A profile's preference is stored as one 512-dimensional vector, in the same CLIP space as `Post.combined_embedding`, produced by taking a weighted average of the embeddings of posts the profile recently interacted with. There is no separate machine-learning model that is trained over time. The vector is recomputed from scratch each time a refresh job runs.

Practically, this means:

- Ranking reduces to "find posts whose vector is closest to the user's vector." That is a single pgvector cosine query against an HNSW index.
- Adding a new signal source (e.g. caption text) only changes how the vector is computed, not how it is used downstream.
- The engine has no persistent learned state. Every request can be reproduced by reading the database and Redis at request time.

### Memory is a sliding window, not convergence

The long-term vector is computed from the last 30 days of interactions, capped to the most recent 500 events, with an exponential half-life of 30 days. It does not converge to a stable representation:

- Interactions older than 30 days are deleted by `cleanup-old-post-interactions` and cannot influence anything.
- Even inside the window, an event from 30 days ago counts half as much as one from today.
- A heavy user (hundreds of interactions per week) has an effectively shorter memory than 30 days because the 500-event cap kicks in first.

If a user's behaviour is consistent, the vector looks stable, but only because the input is. If their interests genuinely shift, the vector follows within roughly 30 to 60 days, faster for power users.

### Multiple interests get averaged into a centroid

Because taste is a single vector, a user with two unrelated interests (say, black labs and parrots) ends up with an embedding at the centroid of those clusters: a point that may not match either cluster well. This is the standard "interest dilution" trade-off of averaged-embedding recommenders.

In practice it works for most users because real-world interests cluster (different cute dogs all live in "dog space"), and MMR re-ranking surfaces some content from each side of a centroid. But for users with sharply distinct engagement patterns, recommendations will feel generic. See "Feed Feels Generic for Users with Multiple Distinct Interests" under Common Failure Modes.

### Short-term taste is a counterweight, not a separate interest

The short-term vector is the same kind of weighted average, but over the last 24 hours with a 12-hour half-life. Blending it with the long-term vector lets the feed react to a current mood swing without erasing past taste, but it is also a single centroid, so multiple simultaneous moods average together too.

The α buckets do **not** preserve separate interests. They only adjust the long/short mix ratio, which is most useful for the time-separated case: long-term "dogs" plus sudden short-term "birds" produces a query vector temporarily nudged toward birds.

### Why this design

Three pressures shape these choices:

- **Speed.** Single-vector cosine search against an HNSW index is fast and cheap. More expressive representations (multi-persona, two-tower models) are an order of magnitude more complex to operate.
- **Freshness.** Background refresh jobs keep vectors current without putting compute on the request path.
- **Simplicity.** No persistent learned state means no model drift across deploys, no training pipeline, and a debug story that fits in a Django shell.

The cost is the centroid limitation. If feed-quality complaints come predominantly from users with diverse engagement patterns, that is the signal to invest in multi-cluster representations.

## Main Components

### `ProfilePreferenceEmbedding`

Defined in `api/apps/recommendations_app/models.py`.

This model stores one long-term taste embedding per profile:

- `profile` - the profile this embedding belongs to.
- `embedding` - a 512-dimensional vector in the same CLIP embedding space as `Post.combined_embedding`.
- `last_computed_at` - when the embedding was last refreshed.
- `interaction_count_at_last_compute` - audit/debug metadata.
- `embedding_model` - model version guard.

The recommendation engine only uses stored long-term embeddings when `embedding_model` matches the current recommendation model constant.

### `PostInteraction`

Defined in `api/apps/interactions_app/models.py`.

This is an append-only event log used as recommendation signal. The same profile can record repeated interactions with the same post.

Supported interaction types:

- `preview_click`
- `view`
- `like`
- `save`
- `comment`

These interactions are the source of truth for both short-term and long-term preference embeddings.

### Embedding Service

Defined in `api/apps/recommendations_app/services.py`.

This module computes user taste vectors from recent `PostInteraction` rows.

Important functions:

- `compute_long_term_embedding(profile)`
- `compute_short_term_embedding(profile)`
- `get_query_embedding(profile)`

Important constants:

- `EMBEDDING_DIM = 512`
- `EMBEDDING_MODEL = "sentence-transformers/clip-ViT-B-32"`
- `LONG_TERM_LOOKBACK_DAYS = 30`
- `SHORT_TERM_LOOKBACK_HOURS = 24`
- `LONG_TERM_MAX_EVENTS = 500`
- `SHORT_TERM_MAX_EVENTS = 50`

## Interaction Weights

Each interaction contributes a weighted signal toward the profile's preference embedding.

| Interaction | Base Weight | Notes |
|-------------|-------------|-------|
| `save` | `5.0` | Strongest positive signal |
| `like` | `3.0` | Strong positive signal |
| `comment` | `2.5` | Strong positive signal |
| `view` | `1.0` | Requires enough dwell time |
| `preview_click` | `0.3` | Weak signal |

Views are ignored unless `dwell_time_ms >= 1500`.

For valid views, dwell time increases the weight:

```text
view_weight = 1.0 * min(1 + dwell_time_ms / 5000, 3.0)
```

This means:

- A short bounce contributes nothing.
- A meaningful view contributes some signal.
- Very long dwell is capped so one view cannot dominate everything.

All interaction weights decay over time using an exponential half-life:

- Long-term half-life: 30 days.
- Short-term half-life: 12 hours.

## Long-Term vs Short-Term Taste

The engine combines two kinds of taste:

### Long-Term Taste

Long-term taste is stored in `ProfilePreferenceEmbedding`.

It is computed from recent interaction history, persisted by Celery, and used as the stable view of what a profile generally likes.

Long-term embeddings are refreshed by background jobs, not directly on every request.

### Short-Term Taste

Short-term taste is computed on demand from the last 24 hours of interactions and cached in Redis for 5 minutes.

It lets the feed react quickly when a user suddenly starts engaging with a new kind of content.

### Blending

`get_query_embedding(profile)` returns the vector used for Explore ranking.

Possible sources:

- `long+short` - both vectors exist and are blended.
- `long_only` - only the stored long-term vector exists.
- `short_only` - only recent interaction signal exists.
- `cold` - no usable signal exists.

When both vectors exist:

```text
query = alpha * long_term + (1 - alpha) * short_term
```

Then the result is L2-normalized.

`alpha` is based on total interaction count:

| Interaction Count | Alpha | Meaning |
|-------------------|-------|---------|
| `< 50` | `0.25` | Newer profiles lean heavily short-term |
| `50 - 199` | `0.45` | Mixed behavior |
| `>= 200` | `0.65` | Mature profiles lean long-term |

## Request-Time Flow

The Explore endpoint is `ListExplorePostsView` in `api/apps/posts_app/views.py`.

Request flow:

1. Client calls `GET /api/v1/post/explore/`.
2. `ExploreCursorPagination.paginate_for_profile()` decodes the cursor.
3. `get_or_create_batch()` checks Redis for an existing batch.
4. If the batch exists, pagination slices IDs from it.
5. If the batch is missing or needs refresh, `generate_explore_batch()` builds a new batch.
6. `get_query_embedding()` decides whether the profile is warm or cold.
7. Warm profiles use vector search.
8. Cold profiles use popularity fallback.
9. If the warm path returns fewer than `BATCH_SIZE` posts, the engine tops up from popularity using the same exclusion set so a sparse vector result does not dead-end infinite scroll.
10. The resulting batch is cached in Redis.
11. The page's returned IDs are recorded in the profile's seen set.

## Cursor and Batch Pagination

Defined in `api/apps/recommendations_app/pagination.py` and `api/apps/recommendations_app/batch.py`.

Important constants:

- `BATCH_SIZE = 300`
- `PAGE_SIZE = 24`
- `BATCH_TTL_SECONDS = 1800`
- `SEEN_TTL_SECONDS = 21600`
- `SEEN_CAP = 5000`

The cursor encodes:

```json
{
  "b": 0,
  "o": 24
}
```

Where:

- `b` is the batch ID.
- `o` is the offset inside that batch.

The response includes:

```json
{
  "next": "https://example.com/api/v1/post/explore/?cursor=...",
  "previous": null,
  "results": [],
  "source": "long+short"
}
```

The `source` field is useful for debugging because it tells you which recommendation path generated the batch.

Common source values:

- `long+short`
- `long_only`
- `short_only`
- `popularity`
- `long+short+popularity`
- `long_only+popularity`
- `short_only+popularity`

The `+popularity` suffix means the vector path produced fewer than 300 posts, so the engine topped up the batch from popularity.

## Vector Recommendation Path

Warm profiles use `generate_explore_batch()`.

The vector path:

1. Builds the query embedding.
2. Finds blocked profile IDs.
3. Excludes own profiles.
4. Excludes followed profiles.
5. Excludes blocked profiles.
6. Excludes heavily reported profiles.
7. Pulls pgvector candidates ordered by cosine distance.
8. Caps results per author profile.
9. Re-ranks with MMR for diversity.
10. Tops up from popularity if needed.

Candidate retrieval uses:

- `recommendable_posts_qs()`
- `CosineDistance("combined_embedding", query_embedding)`
- `SET LOCAL hnsw.ef_search = 200`

The engine pulls `BATCH_SIZE * CANDIDATE_PULL_MULTIPLIER`, currently 600 candidates, to produce up to 300 final IDs.

### Recommendable Posts

`recommendable_posts_qs()` centralizes baseline eligibility:

- Post must be `READY`.
- Profile must be public.
- Post must not have an inappropriate-content report.

Only the `INAPPROPRIATE_REPORT_REASON_NAME` report reason gates eligibility. Other report reasons (e.g. "Not Pet Related", "Other") do **not** auto-suppress a post; they are surfaced to moderation but the post stays in Explore. This matches the policy used by the followed feed, profile views, and similar-posts. Heavily-reported *profiles* are filtered separately at the request layer.

The same helper is used by every path that surfaces posts to a viewer (vector search, popularity refresh, popularity revalidation, recency safety net) so eligibility cannot drift between paths. If you change the rules, change them here.

Additional request-specific filters happen in `generate_explore_batch()`:

- Exclude posts from the current user's own profiles.
- Exclude followed profiles.
- Exclude blocked profiles.
- Exclude heavily reported profiles.
- Exclude recently seen posts for continuation batches.

### Per-Profile Cap

`MAX_PER_PROFILE = 5`.

After candidates are retrieved, `_cap_per_profile()` prevents one author from dominating the batch.

### MMR Diversification

`_mmr_select()` applies Maximal Marginal Relevance.

The scoring idea is:

```text
score = similarity_to_query - lambda * similarity_to_already_selected_posts
```

This keeps results close to the user's taste while reducing near-duplicates.

### Top-Up When Vector Underfills

The vector path can return fewer than `BATCH_SIZE` posts when:

- The user has a large `seen` set (mid-scroll, or heavy historical use).
- The user follows a large fraction of public posters, eliminating most candidates.
- The user's preference embedding is in a sparse region (very niche taste).
- A combination of the above.

Without top-up, infinite scroll dead-ends with a half-empty stack. The engine therefore calls `get_popularity_fallback_ids()` with `excluded_profile_ids=excluded_profile_ids` so the popularity backfill respects the same own / followed / blocked / heavily-reported filters the vector path applied. Picks already chosen by the vector path are de-duplicated.

The `source` field tells you which mode happened:

| Vector result | Topup added | Source label |
|---------------|-------------|--------------|
| Full batch | 0 | original (e.g. `long+short`) |
| Partial | 1+ | `<original>+popularity` |
| Empty | 1+ | `popularity` |
| Empty | 0 | original (so logs distinguish "starved" from "cold") |

## Popularity Fallback

Defined in `api/apps/recommendations_app/popularity.py`.

Popularity is used when:

- The profile is cold.
- The vector path returns no candidates.
- The vector path returns fewer than `BATCH_SIZE` candidates.

The popularity cache is a Redis sorted set:

```text
rec:popular_posts:7d
```

`refresh_popularity_set()` recomputes the top posts over the last 7 days.

Popularity score:

```text
(likes + 3*saves + 2.5*comments + 0.5*views) / age_hours^1.5
```

Age is floored at 1 hour so brand-new posts do not explode in score.

If the popularity Redis set is empty, the system falls back to recent eligible posts.

The fallback path revalidates post IDs through `recommendable_posts_qs()` before returning them. This prevents stale Redis popularity entries from leaking newly reported inappropriate posts.

## Seen Tracking

Seen tracking is stored in Redis as a sorted set:

```text
rec:seen:{profile_id}
```

The score is the timestamp when the post was delivered or confirmed as engaged.

Seen IDs are used differently depending on pagination state:

- First load of batch `0`: does not exclude seen IDs, so the top of feed is populated.
- Cursorless refresh of batch `0`: may regenerate when the first page has already been seen.
- Batch `>= 1`: excludes recently seen IDs so infinite scroll favors fresh content.

When a user records a meaningful view, like, save, or comment, the seen set is bumped so genuinely viewed content persists longer than delivery-only entries.

## Cache Keys

Useful Redis keys:

| Key | Purpose |
|-----|---------|
| `rec:batch:{profile_id}:{batch_id}` | Cached list of post IDs for a batch |
| `rec:batch_meta:{profile_id}:{batch_id}` | Source label for the batch |
| `rec:seen:{profile_id}` | Recently delivered or engaged post IDs |
| `rec:short_term:{profile_id}` | Cached short-term embedding |
| `rec:int_count:{profile_id}` | Cached interaction count for alpha selection |
| `rec:popular_posts:7d` | Popularity sorted set |
| `rec:heavily_reported_profile_ids` | Cached profile-level moderation exclusions |
| `rec:refresh_generation:{profile_id}` | Token used to vary refreshed first batches |

## Signals

Defined in `api/apps/recommendations_app/signals.py`.

When a new `PostInteraction` is created, the signal:

1. Deletes the short-term embedding cache.
2. Deletes the cached interaction count.
3. Deletes batch `0` and its metadata.
4. Bumps the seen set for meaningful views and high-intent interactions.

Only batch `0` is invalidated. Mid-scroll batches are intentionally left alone so the user's continuation pages do not reshuffle unexpectedly.

## Background Jobs

Defined in `api/apps/recommendations_app/tasks.py`.

Configured in:

- `api/core/celery.py`
- `api/core/settings.py`

### `update_profile_preference_embedding_task`

Recomputes one profile's long-term preference embedding.

Behavior:

- Creates or updates `ProfilePreferenceEmbedding`.
- Stores the current embedding model name.
- Stores interaction count metadata.
- Preserves an existing valid embedding if the new computation has no signal.
- Retries up to 3 times on unexpected errors.

### `update_stale_preference_embeddings_task`

Runs every 6 hours.

Finds profiles with activity in the last 24 hours whose embeddings are missing or older than 6 hours, then queues per-profile refresh tasks.

Tasks are spread over time to avoid dumping too many jobs into the broker at once.

### `nightly_preference_embedding_refresh_task`

Runs daily at 2:00 UTC.

This is a safety-net refresh for profiles with interactions in the last 7 days.

### `refresh_popularity_cache_task`

Runs every 30 minutes.

Rebuilds `rec:popular_posts:7d`.

### `refresh_heavily_reported_profiles_task`

Runs every 5 minutes.

Caches profile IDs with at least 5 open profile reports. These profiles are excluded from the vector path and from popularity top-up when the vector path passes its exclusion set through.

## Debugging Guide

### Start With the API Response

Call Explore and check `source`:

```bash
curl -H "Authorization: Bearer <token>" \
  -H "X-Profile-ID: <profile_public_id>" \
  http://localhost:8000/api/v1/post/explore/
```

Interpretation:

| Source | Meaning |
|--------|---------|
| `popularity` | No usable personalization, or vector path returned zero candidates |
| `short_only` | Recent interactions exist, but no usable long-term embedding |
| `long_only` | Stored long-term embedding exists, but no usable short-term signal |
| `long+short` | Fully personalized path |
| `*+popularity` | Personalized path underfilled and was topped up |

### If the Feed Is Using `popularity` Unexpectedly

Check whether the profile has a usable long-term embedding:

```bash
docker exec onlypaws_django python api/manage.py shell
```

```python
from apps.profile_app.models import Profile
from apps.recommendations_app.models import ProfilePreferenceEmbedding
from apps.recommendations_app.services import EMBEDDING_MODEL, get_query_embedding

profile = Profile.objects.get(public_id="<profile_public_id>")
pref = ProfilePreferenceEmbedding.objects.filter(profile=profile).first()

print(pref is not None)
print(pref.embedding is not None if pref else None)
print(pref.embedding_model if pref else None)
print(EMBEDDING_MODEL)
print(get_query_embedding(profile)[1])
```

Things to check:

- Is the row missing?
- Is `embedding` null?
- Does `embedding_model` mismatch?
- Does `get_query_embedding(profile)` return `cold`?

### If There Is No Long-Term Embedding

Check recent interactions:

```python
from apps.interactions_app.models import PostInteraction

PostInteraction.objects.filter(profile=profile).order_by("-created_at")[:20].values(
    "post_id",
    "interaction_type",
    "dwell_time_ms",
    "created_at",
)
```

Then manually run the task:

```python
from apps.recommendations_app.tasks import update_profile_preference_embedding_task

update_profile_preference_embedding_task(profile.id)
```

Re-check `ProfilePreferenceEmbedding`.

### If Interactions Exist But Embedding Is Still Null

Check whether the interacted posts have valid combined embeddings:

```python
from apps.posts_app.models import Post
from apps.recommendations_app.services import EMBEDDING_MODEL

post_ids = list(
    PostInteraction.objects.filter(profile=profile)
    .values_list("post_id", flat=True)
    .distinct()
)

Post.objects.filter(id__in=post_ids).values(
    "id",
    "status",
    "combined_embedding_model",
    "combined_embedding",
)
```

Likely causes:

- Posts are not `READY`.
- Posts do not have `combined_embedding`.
- Posts were embedded with a different model.
- Total weighted signal is below threshold.
- Views are below the dwell-time threshold.

### If Short-Term Taste Is Not Updating

Check that new `PostInteraction` rows are being created.

Then check whether the short-term cache was invalidated:

```python
from django.core.cache import cache
from apps.recommendations_app.services import short_term_cache_key

cache.get(short_term_cache_key(profile.id))
```

If this returns a vector or `"none"` immediately after new interactions, the signal may not have invalidated correctly or the interaction was not created.

### If Results Repeat Too Much

Inspect seen IDs:

```python
from apps.recommendations_app.batch import get_seen_post_ids

get_seen_post_ids(profile)[:50]
```

Things to check:

- Is Redis running and preserving `rec:seen:{profile_id}`?
- Is pagination calling `record_seen_post_ids()`?
- Is the client repeatedly requesting the first page without cursor?
- Are there too few eligible posts after filters?

### If the Feed Is Empty

Check each layer in order:

1. Does `get_query_embedding(profile)` return a vector or `cold`?
2. Are there any recommendable posts?
3. Are eligible posts excluded by own/followed/blocked/heavily-reported filters?
4. Do eligible posts have matching `combined_embedding_model`?
5. Is the seen set excluding most available content?
6. Is `rec:popular_posts:7d` populated?
7. Does recency fallback have any eligible public `READY` posts?

Useful shell checks:

```python
from apps.recommendations_app.queryset_utils import recommendable_posts_qs

recommendable_posts_qs().count()
recommendable_posts_qs().filter(combined_embedding__isnull=False).count()
```

### If Popularity Looks Wrong

Check the Redis popularity set:

```python
from apps.recommendations_app.popularity import POPULARITY_KEY, _redis_client

client = _redis_client()
client.zrevrange(POPULARITY_KEY, 0, 20, withscores=True)
```

Manually refresh it:

```python
from apps.recommendations_app.popularity import refresh_popularity_set

refresh_popularity_set()
```

If the set is empty:

- There may be no engagement in the last 7 days.
- Candidate posts may not be `READY`.
- Candidate posts may be private or reported.
- The refresh task may not be running.

### If Heavily Reported Profiles Still Appear

Check the cache:

```python
from django.core.cache import cache
from apps.recommendations_app.batch import HEAVY_REPORTED_CACHE_KEY

cache.get(HEAVY_REPORTED_CACHE_KEY)
```

Manually refresh:

```python
from apps.recommendations_app.tasks import refresh_heavily_reported_profiles_task

refresh_heavily_reported_profiles_task()
```

Important limitation: if this cache is cold, the request path fails open to `[]` instead of running an expensive aggregation synchronously.

### If Cursor Pagination Behaves Oddly

Remember:

- No cursor means batch `0`, offset `0`, and `refresh=True`.
- A cursor contains batch ID and offset.
- End of one batch returns a cursor for the next batch.
- Empty mid-scroll batches can self-heal by advancing to the next batch.

If needed, decode a cursor:

```python
from apps.recommendations_app.pagination import _decode_cursor

_decode_cursor("<cursor>")
```

## Common Failure Modes

### 1. Cold Start Falls Back to Recency

Symptoms:

- Response source is `popularity`.
- Logs say popularity Redis set is empty.
- Results are ordered like recent posts.

Likely cause:

- `refresh_popularity_cache_task` has not populated Redis yet.

Fix:

- Run `refresh_popularity_set()`.
- Confirm Celery Beat is running.

### 2. Long-Term Taste Feels Stale

Symptoms:

- User recently changed behavior.
- Feed still reflects older interests.
- Source is `long_only` or `long+short`, but short-term signal is weak.

Likely cause:

- Long-term embedding refresh is asynchronous.
- Short-term signal threshold may not be met.

Fix:

- Check recent interactions.
- Check short-term cache.
- Manually run `update_profile_preference_embedding_task(profile.id)`.

### 3. User Sees Too Much Similar Content

Symptoms:

- Same profile dominates results.
- Many near-duplicate posts appear.

Likely cause:

- Candidate pool is small after filters.
- `MAX_PER_PROFILE` still allows up to 5 posts per author.
- MMR only diversifies within embedding space.

Fix:

- Inspect eligible candidate counts.
- Tune `MAX_PER_PROFILE`.
- Tune `MMR_LAMBDA`.

### 4. User Sees Content From Followed Profiles

Symptoms:

- Explore includes posts from profiles the user already follows.

Likely cause:

- Bug in `_followed_profile_ids()` or top-up exclusion propagation.

Fix:

- Check `Follow` rows for the profile.
- Confirm `excluded_profile_ids` is passed into `get_popularity_fallback_ids()` during top-up.

### 5. Profile Has Interactions But No Embedding

Symptoms:

- `PostInteraction` rows exist.
- `ProfilePreferenceEmbedding.embedding` is null.

Likely cause:

- Signal strength below threshold.
- Interacted posts do not have valid combined embeddings.
- Interacted posts are not `READY`.
- Embedding model mismatch.

Fix:

- Inspect interaction types and dwell time.
- Inspect post embedding fields.
- Run the per-profile refresh task manually.

### 6. Feed Feels Generic for Users with Multiple Distinct Interests

Symptoms:

- A user's `PostInteraction` history clearly spans two or more distinct content clusters (e.g. dogs and reptiles).
- Explore returns posts that match neither cluster especially well.
- Source is `long_only` or `long+short`, so the personalization path is running, but quality feels mediocre.

Likely cause:

- The single averaged preference vector is a centroid between the user's interest clusters.
- MMR diversifies the candidate set but cannot recover from a query vector pointed at a "no man's land" between clusters. See "Multiple interests get averaged into a centroid" in Conceptual Model.

Fix:

- This is an architectural limitation, not a bug. There is no per-request fix.
- A recent burst of activity in one cluster will pull the blended vector toward that cluster temporarily, partially mitigating dilution while the user is engaging there.
- Long-term mitigation requires multi-cluster user representations. See "Limitations and Future Improvements."

## Useful Logs

Search for these logger names or message fragments:

- `apps.recommendations_app.batch`
- `apps.recommendations_app.popularity`
- `apps.recommendations_app.tasks`
- `explore batch profile=`
- `source=popularity`
- `selected=`
- `topup=`
- `Popularity Redis set empty`
- `Updated preference embedding`
- `No fresh signal`

Example batch log:

```text
explore batch profile=1 batch_id=0 source=long+short+popularity pulled=600 capped=300 selected=300 topup=42
```

Fields:

- `source` - ranking path used.
- `pulled` - raw vector candidates pulled from pgvector.
- `capped` - candidates remaining after per-profile cap.
- `selected` - final batch size.
- `topup` - number of popularity fallback IDs added.

## Tests

Recommendation behavior is covered by:

- `api/apps/recommendations_app/tests/test_services.py`
- `api/apps/recommendations_app/tests/test_batch.py`
- `api/apps/recommendations_app/tests/test_popularity.py`
- `api/apps/recommendations_app/tests/test_pagination.py`
- `api/apps/recommendations_app/tests/test_tasks.py`
- `api/apps/recommendations_app/tests/test_queryset_utils.py`
- `api/apps/posts_app/tests/test_explore_api.py`

Run recommendation tests:

```bash
scripts/test.sh recommendations_app
```

Run Explore API tests:

```bash
scripts/test.sh posts_app
```

## Limitations and Future Improvements

Current limitations:

- **Single-vector taste representation.** Users with multiple distinct interest clusters get a centroid that may not match any cluster well. See Conceptual Model and Failure Mode 6.
- **Sliding-window memory, not learned.** Long-term embeddings are recomputed from scratch each refresh, bounded by `PostInteraction` retention (30 days) and `LONG_TERM_MAX_EVENTS` (500). The system has no way to remember signal older than the window.
- **No negative feedback signal yet.** Likes, saves, comments, and engaged views all count positively; there is no "not interested" pathway.
- **Asynchronous refresh.** Long-term embeddings update on a 6-hourly sweep, not immediately after each interaction. Short-term taste reacts faster but is gated by a minimum signal threshold.
- **Cold-start quality depends on the popularity cache.** Until `refresh_popularity_cache_task` runs, cold users get the recency safety net only.
- **Redis eviction sensitivity.** Batches, popularity, and seen sets all live in Redis. Eviction or outages degrade quality silently.
- **Heavily-reported profile filtering fails open** when its cache is cold, so a beat outage can briefly let heavily-reported profiles surface.
- **Popularity staleness.** The popularity ranking can be up to 30 minutes behind. Newly-reported posts on the popularity set are caught by request-time revalidation, but engagement-based reordering is not.
- **MMR diversity is similarity-only.** It cannot enforce explicit content-category diversity.
- **Embedding quality assumed good.** The engine has no defense against poor or mis-clustered `Post.combined_embedding` values upstream.

Potential future improvements:

- Multi-cluster user representations (k-means over interactions, multiple personas) to address the centroid limitation.
- Negative feedback such as "not interested" or "show less like this."
- Explicit category or pet-type diversity in re-ranking.
- Track recommendation impressions separately from confirmed views.
- Admin/debug endpoints for a profile's recommendation state.
- Metrics for source distribution, vector underfill rate, popularity fallback rate, and centroid drift.
- Automatic per-profile refresh after high-intent interaction bursts.
- Exploration logic so users are not locked into one taste cluster.

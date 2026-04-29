"""
Tests for batch generation and cursor-batch helpers.
"""

from types import SimpleNamespace
from unittest import mock

import numpy as np
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.interactions_app.models import PostInteraction
from apps.posts_app.models import Post
from apps.recommendations_app.batch import (
    BATCH_SIZE,
    MAX_PER_PROFILE,
    _batch_key,
    _batch_meta_key,
    _cap_per_profile,
    _mmr_select,
    _select_with_seen_backfill,
    generate_explore_batch,
    get_or_create_batch,
)
from apps.recommendations_app.models import ProfilePreferenceEmbedding
from apps.recommendations_app.services import EMBEDDING_DIM, EMBEDDING_MODEL
from core.test_utils.helper_classes import BaseFixtureTestCase
from core.test_utils.utils import create_mock_embedding


IT = PostInteraction.InteractionType


def _set_post_embedding(post, embedding):
    post.combined_embedding = embedding
    post.combined_embedding_model = EMBEDDING_MODEL
    post.combined_embedding_generated_at = timezone.now()
    post.status = Post.Status.READY
    post.save(
        update_fields=[
            "combined_embedding",
            "combined_embedding_model",
            "combined_embedding_generated_at",
            "status",
        ]
    )


def _normed(seed):
    v = np.asarray(
        create_mock_embedding(seed=seed, dimensions=EMBEDDING_DIM), dtype=np.float64
    )
    return (v / np.linalg.norm(v)).tolist()


class CapPerProfileTests(TestCase):

    def test_caps_to_limit_in_order(self):
        candidates = [
            (1, 100, [0.1] * EMBEDDING_DIM),
            (2, 100, [0.2] * EMBEDDING_DIM),
            (3, 100, [0.3] * EMBEDDING_DIM),  # exceeds cap of 2
            (4, 200, [0.4] * EMBEDDING_DIM),
        ]
        result = _cap_per_profile(candidates, max_per_profile=2)
        self.assertEqual([c[0] for c in result], [1, 2, 4])

    def test_preserves_order(self):
        # When candidates are interleaved, output keeps relative ordering.
        candidates = [
            (10, 100, [0.0] * EMBEDDING_DIM),
            (20, 200, [0.0] * EMBEDDING_DIM),
            (30, 100, [0.0] * EMBEDDING_DIM),
            (40, 100, [0.0] * EMBEDDING_DIM),  # over cap
            (50, 200, [0.0] * EMBEDDING_DIM),
        ]
        result = _cap_per_profile(candidates, max_per_profile=2)
        self.assertEqual([c[0] for c in result], [10, 20, 30, 50])


class MMRSelectTests(TestCase):

    def test_returns_at_most_target_size(self):
        candidates = [(i, 0, _normed(i)) for i in range(10)]
        query = np.asarray(_normed(0))
        selected = _mmr_select(candidates, query, target_size=5)
        self.assertEqual(len(selected), 5)

    def test_first_pick_is_highest_query_similarity(self):
        candidates = [(i, 0, _normed(i)) for i in range(10)]
        query = np.asarray(_normed(0))
        # The candidate built from the same seed as the query should be picked first.
        selected = _mmr_select(candidates, query, target_size=1)
        self.assertEqual(selected, [0])

    def test_handles_empty_candidates(self):
        self.assertEqual(_mmr_select([], np.zeros(EMBEDDING_DIM), target_size=10), [])

    def test_zero_query_falls_back_to_input_order(self):
        candidates = [(i, 0, _normed(i)) for i in range(5)]
        selected = _mmr_select(candidates, np.zeros(EMBEDDING_DIM), target_size=3)
        self.assertEqual(selected, [0, 1, 2])


class SeenBackfillTests(TestCase):

    def test_prefers_unseen_posts_before_seen_backfill(self):
        candidates = [
            (1, 100, [0.0] * EMBEDDING_DIM),
            (2, 200, [0.0] * EMBEDDING_DIM),
            (3, 300, [0.0] * EMBEDDING_DIM),
            (4, 400, [0.0] * EMBEDDING_DIM),
        ]

        selected = _select_with_seen_backfill(
            candidates,
            np.zeros(EMBEDDING_DIM),
            target_size=3,
            seen_ids={3, 4},
        )

        self.assertEqual(selected, [1, 2, 3])

    def test_backfills_seen_posts_when_inventory_is_small(self):
        candidates = [
            (1, 100, [0.0] * EMBEDDING_DIM),
            (2, 200, [0.0] * EMBEDDING_DIM),
            (3, 300, [0.0] * EMBEDDING_DIM),
        ]

        selected = _select_with_seen_backfill(
            candidates,
            np.zeros(EMBEDDING_DIM),
            target_size=3,
            seen_ids={1, 2, 3},
        )

        self.assertEqual(selected, [1, 2, 3])


class GetOrCreateBatchTests(TestCase):

    def setUp(self):
        self.profile = SimpleNamespace(id=123)
        cache.delete(_batch_key(self.profile.id, 0))
        cache.delete(_batch_meta_key(self.profile.id, 0))

    def tearDown(self):
        cache.delete(_batch_key(self.profile.id, 0))
        cache.delete(_batch_meta_key(self.profile.id, 0))

    def test_refresh_regenerates_seen_first_page_with_backfill_enabled(self):
        cached_ids = list(range(1, 31))
        cache.set(_batch_key(self.profile.id, 0), cached_ids)
        cache.set(_batch_meta_key(self.profile.id, 0), "popularity")

        with mock.patch(
            "apps.recommendations_app.batch.get_seen_post_ids",
            return_value=cached_ids[:24],
        ), mock.patch(
            "apps.recommendations_app.batch._next_refresh_generation",
            return_value=7,
        ), mock.patch(
            "apps.recommendations_app.batch.generate_explore_batch",
            return_value=([101, 102], "popularity"),
        ) as generate:
            ids, source = get_or_create_batch(self.profile, 0, refresh=True)

        self.assertEqual(ids, [101, 102])
        self.assertEqual(source, "popularity")
        generate.assert_called_once_with(
            self.profile,
            0,
            cached_ids[:24],
            allow_seen_backfill=True,
            refresh_generation=7,
        )


class GenerateExploreBatchTests(BaseFixtureTestCase):
    """Integration tests that exercise the full batch pipeline against pgvector."""

    def setUp(self):
        super().setUp()
        # Seed all 8 fixture posts with identifiable embeddings.
        # Cluster A: posts 5, 6 (seeds 1, 1)
        # Cluster B: posts 7, 8 (seeds 999, 999)
        cluster_a = create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        cluster_b = create_mock_embedding(seed=999, dimensions=EMBEDDING_DIM)
        for post in (self.post_1, self.post_2, self.post_3, self.post_4):
            _set_post_embedding(post, cluster_a)
        _set_post_embedding(self.post_5, cluster_a)
        _set_post_embedding(self.post_6, cluster_a)
        _set_post_embedding(self.post_7, cluster_b)
        _set_post_embedding(self.post_8, cluster_b)

        # Seed a long-term embedding for self.profile pointing at cluster_a.
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=cluster_a,
            last_computed_at=timezone.now(),
            embedding_model=EMBEDDING_MODEL,
            interaction_count_at_last_compute=300,
        )

    def test_excludes_own_posts(self):
        ids, _ = generate_explore_batch(
            self.profile, batch_id=0, exclude_post_ids=set()
        )
        own_ids = {self.post_1.id, self.post_2.id}
        self.assertFalse(own_ids & set(ids))

    def test_excludes_followed_profiles(self):
        # self.profile follows self.profile_2 (post_3, post_4).
        ids, _ = generate_explore_batch(
            self.profile, batch_id=0, exclude_post_ids=set()
        )
        followed_ids = {self.post_3.id, self.post_4.id}
        self.assertFalse(followed_ids & set(ids))

    def test_excludes_reported_posts(self):
        # post_4 has been reported in the fixture; it's already excluded by
        # follows above, but post_1 is also reported and own — covered.
        ids, _ = generate_explore_batch(
            self.profile, batch_id=0, exclude_post_ids=set()
        )
        # Any post with reports should be absent. post_1 (reported, own) and
        # post_4 (reported, followed) are both already filtered for other reasons,
        # but the call should still complete and respect the report filter.
        for pid in ids:
            post = Post.objects.get(pk=pid)
            self.assertEqual(post.reports.count(), 0)

    def test_excludes_explicit_exclude_set(self):
        ids, _ = generate_explore_batch(
            self.profile, batch_id=0, exclude_post_ids={self.post_5.id}
        )
        self.assertNotIn(self.post_5.id, ids)

    def test_returns_eligible_posts(self):
        # With cluster_a profile pref: posts 5, 6, 7, 8 are eligible (5/6 same-cluster, 7/8 other).
        ids, source = generate_explore_batch(
            self.profile, batch_id=0, exclude_post_ids=set()
        )
        self.assertGreater(len(ids), 0)
        self.assertLessEqual(len(ids), BATCH_SIZE)
        self.assertIn(source, ("long+short", "long_only", "short_only"))

    def test_cold_profile_falls_back_to_popularity(self):
        # Wipe profile_3's pref + interactions so it's cold.
        ProfilePreferenceEmbedding.objects.filter(profile=self.profile_3).delete()
        PostInteraction.objects.filter(profile=self.profile_3).delete()

        ids, source = generate_explore_batch(
            self.profile_3, batch_id=0, exclude_post_ids=set()
        )
        self.assertEqual(source, "popularity")

"""
Tests for the recommendation embedding service.
"""

from datetime import timedelta
from unittest import mock

import numpy as np
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.interactions_app.models import PostInteraction
from apps.posts_app.models import Post
from apps.recommendations_app import services
from apps.recommendations_app.models import ProfilePreferenceEmbedding
from apps.recommendations_app.services import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    _alpha_for,
    _weight_for,
    compute_long_term_embedding,
    compute_short_term_embedding,
    get_query_embedding,
    short_term_cache_key,
)
from core.test_utils.helper_classes import BaseFixtureTestCase
from core.test_utils.utils import create_mock_embedding


IT = PostInteraction.InteractionType


def _set_post_embedding(post, embedding, model=EMBEDDING_MODEL):
    """Force a post into READY status with a combined embedding for tests."""
    post.combined_embedding = embedding
    post.combined_embedding_model = model
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


class WeightMathTests(TestCase):
    """Pure-function tests for the per-event weight formula."""

    def test_save_at_zero_age_uses_full_type_weight(self):
        self.assertAlmostEqual(_weight_for(IT.SAVE, None, 0, 30 * 86400), 5.0)

    def test_like_at_zero_age(self):
        self.assertAlmostEqual(_weight_for(IT.LIKE, None, 0, 30 * 86400), 3.0)

    def test_preview_click_at_zero_age(self):
        self.assertAlmostEqual(_weight_for(IT.PREVIEW_CLICK, None, 0, 30 * 86400), 0.3)

    def test_one_half_life_halves_weight(self):
        half = 30 * 86400
        self.assertAlmostEqual(_weight_for(IT.SAVE, None, half, half), 2.5)

    def test_view_without_dwell_returns_zero(self):
        self.assertEqual(_weight_for(IT.VIEW, None, 0, 30 * 86400), 0.0)

    def test_view_with_short_dwell_is_treated_as_bounce(self):
        self.assertEqual(_weight_for(IT.VIEW, 1000, 0, 30 * 86400), 0.0)

    def test_view_dwell_multiplier(self):
        # dwell 5000ms => multiplier (1 + 5000/5000) = 2.0; weight = 1.0 * 2.0 = 2.0
        self.assertAlmostEqual(_weight_for(IT.VIEW, 5000, 0, 30 * 86400), 2.0)

    def test_view_dwell_multiplier_capped(self):
        self.assertAlmostEqual(_weight_for(IT.VIEW, 60000, 0, 30 * 86400), 3.0)


class AlphaTests(TestCase):

    def test_below_50_returns_short_term_lean(self):
        self.assertEqual(_alpha_for(0), 0.25)
        self.assertEqual(_alpha_for(49), 0.25)

    def test_50_to_200_returns_mid(self):
        self.assertEqual(_alpha_for(50), 0.45)
        self.assertEqual(_alpha_for(199), 0.45)

    def test_at_or_above_200_returns_default(self):
        self.assertEqual(_alpha_for(200), 0.65)
        self.assertEqual(_alpha_for(10_000), 0.65)


class LongTermEmbeddingTests(BaseFixtureTestCase):
    """End-to-end tests for compute_long_term_embedding."""

    def setUp(self):
        super().setUp()
        # Seed embeddings on posts 5/6/7/8 (the ones explore would surface).
        # Posts 5 & 6 share a "cluster" by deriving from the same base seed.
        self.cluster_a = create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        self.cluster_b = create_mock_embedding(seed=999, dimensions=EMBEDDING_DIM)
        _set_post_embedding(self.post_5, self.cluster_a)
        _set_post_embedding(self.post_6, self.cluster_a)
        _set_post_embedding(self.post_7, self.cluster_b)
        _set_post_embedding(self.post_8, self.cluster_b)

    def _create_interaction(
        self, profile, post, interaction_type, dwell_ms=None, age_seconds=0
    ):
        obj = PostInteraction.objects.create(
            profile=profile,
            post=post,
            interaction_type=interaction_type,
            dwell_time_ms=dwell_ms,
        )
        if age_seconds:
            new_ts = timezone.now() - timedelta(seconds=age_seconds)
            PostInteraction.objects.filter(pk=obj.pk).update(created_at=new_ts)
        return obj

    def test_returns_none_for_profile_with_no_interactions(self):
        self.assertIsNone(compute_long_term_embedding(self.profile))

    def test_returns_none_when_signal_below_threshold(self):
        # One PREVIEW_CLICK = 0.3 weight, well under MIN_WEIGHTED_SIGNAL=5.0.
        self._create_interaction(self.profile, self.post_5, IT.PREVIEW_CLICK)
        self.assertIsNone(compute_long_term_embedding(self.profile))

    def test_strong_signal_produces_l2_normalised_vector(self):
        # SAVE (5.0) + LIKE (3.0) = 8.0 weighted, above threshold.
        self._create_interaction(self.profile, self.post_5, IT.SAVE)
        self._create_interaction(self.profile, self.post_6, IT.LIKE)

        vec = compute_long_term_embedding(self.profile)
        self.assertIsNotNone(vec)
        self.assertEqual(vec.shape, (EMBEDDING_DIM,))
        self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=5)

    def test_skips_posts_with_mismatched_embedding_model(self):
        _set_post_embedding(self.post_5, self.cluster_a, model="some-other-model")
        _set_post_embedding(self.post_6, self.cluster_a, model="some-other-model")
        # Both signal-worthy interactions point at posts the engine should ignore.
        self._create_interaction(self.profile, self.post_5, IT.SAVE)
        self._create_interaction(self.profile, self.post_6, IT.SAVE)
        self.assertIsNone(compute_long_term_embedding(self.profile))

    def test_pulls_toward_dominant_cluster(self):
        # Strong signal on cluster_a; no signal on cluster_b.
        self._create_interaction(self.profile, self.post_5, IT.SAVE)
        self._create_interaction(self.profile, self.post_6, IT.SAVE)

        vec = compute_long_term_embedding(self.profile)
        self.assertIsNotNone(vec)
        # Cosine similarity to cluster_a should be much higher than to cluster_b.
        a = np.asarray(self.cluster_a)
        a /= np.linalg.norm(a)
        b = np.asarray(self.cluster_b)
        b /= np.linalg.norm(b)
        sim_a = float(np.dot(vec, a))
        sim_b = float(np.dot(vec, b))
        self.assertGreater(sim_a, sim_b)


class ShortTermEmbeddingCachingTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        cache.delete(short_term_cache_key(self.profile.id))
        _set_post_embedding(
            self.post_5, create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        )
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )

    def test_cache_hit_skips_recompute(self):
        with mock.patch.object(
            services,
            "_compute_weighted_average",
            wraps=services._compute_weighted_average,
        ) as spy:
            first = compute_short_term_embedding(self.profile)
            second = compute_short_term_embedding(self.profile)
        self.assertIsNotNone(first)
        np.testing.assert_array_equal(first, second)
        # Spy should have been called only on the first invocation.
        self.assertEqual(spy.call_count, 1)

    def test_no_signal_cached_as_sentinel(self):
        # Wipe interactions so the recompute returns None.
        PostInteraction.objects.filter(profile=self.profile).delete()
        cache.delete(short_term_cache_key(self.profile.id))

        first = compute_short_term_embedding(self.profile)
        self.assertIsNone(first)

        # Second call should hit the sentinel without recomputing.
        with mock.patch.object(services, "_compute_weighted_average") as recompute:
            second = compute_short_term_embedding(self.profile)
        self.assertIsNone(second)
        recompute.assert_not_called()


class GetQueryEmbeddingTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        cache.delete(short_term_cache_key(self.profile.id))
        _set_post_embedding(
            self.post_5, create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        )
        _set_post_embedding(
            self.post_6, create_mock_embedding(seed=2, dimensions=EMBEDDING_DIM)
        )

    def test_cold_when_no_signal_anywhere(self):
        vec, source = get_query_embedding(self.profile)
        self.assertIsNone(vec)
        self.assertEqual(source, "cold")

    def test_short_only_when_recent_signal_no_long_term_row(self):
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )
        vec, source = get_query_embedding(self.profile)
        self.assertEqual(source, "short_only")
        self.assertEqual(vec.shape, (EMBEDDING_DIM,))

    def test_short_only_activates_on_recent_like_without_long_term_row(self):
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.LIKE
        )
        vec, source = get_query_embedding(self.profile)
        self.assertEqual(source, "short_only")
        self.assertEqual(vec.shape, (EMBEDDING_DIM,))

    def test_long_only_when_short_term_window_empty(self):
        # Stash a precomputed long-term embedding without any short-term signal.
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=create_mock_embedding(seed=3, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now(),
            embedding_model=EMBEDDING_MODEL,
            interaction_count_at_last_compute=300,
        )
        vec, source = get_query_embedding(self.profile)
        self.assertEqual(source, "long_only")
        self.assertEqual(vec.shape, (EMBEDDING_DIM,))

    def test_blends_when_both_present(self):
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=create_mock_embedding(seed=3, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now(),
            embedding_model=EMBEDDING_MODEL,
            interaction_count_at_last_compute=300,
        )
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )
        vec, source = get_query_embedding(self.profile)
        self.assertEqual(source, "long+short")
        self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=5)

    def test_skips_long_when_embedding_model_mismatches(self):
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=create_mock_embedding(seed=3, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now(),
            embedding_model="some-other-model",
            interaction_count_at_last_compute=300,
        )
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )
        vec, source = get_query_embedding(self.profile)
        self.assertEqual(source, "short_only")

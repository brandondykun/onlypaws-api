"""
Tests for recommendation Celery tasks.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.interactions_app.models import PostInteraction
from apps.posts_app.models import Post
from apps.recommendations_app.models import ProfilePreferenceEmbedding
from apps.recommendations_app.services import EMBEDDING_DIM, EMBEDDING_MODEL
from apps.recommendations_app.tasks import (
    nightly_preference_embedding_refresh_task,
    update_profile_preference_embedding_task,
    update_stale_preference_embeddings_task,
)
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


class UpdateProfilePreferenceEmbeddingTaskTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        _set_post_embedding(
            self.post_5, create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        )
        _set_post_embedding(
            self.post_6, create_mock_embedding(seed=2, dimensions=EMBEDDING_DIM)
        )

    def test_creates_row_for_first_run(self):
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )
        update_profile_preference_embedding_task(self.profile.id)

        pref = ProfilePreferenceEmbedding.objects.get(profile=self.profile)
        self.assertIsNotNone(pref.embedding)
        self.assertIsNotNone(pref.last_computed_at)
        self.assertEqual(pref.embedding_model, EMBEDDING_MODEL)
        self.assertGreaterEqual(pref.interaction_count_at_last_compute, 1)

    def test_updates_existing_row_on_subsequent_run(self):
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=create_mock_embedding(seed=99, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now() - timedelta(days=1),
            interaction_count_at_last_compute=10,
        )
        PostInteraction.objects.create(
            profile=self.profile, post=self.post_5, interaction_type=IT.SAVE
        )
        update_profile_preference_embedding_task(self.profile.id)

        pref = ProfilePreferenceEmbedding.objects.get(profile=self.profile)
        # last_computed_at should advance.
        self.assertGreater(pref.last_computed_at, timezone.now() - timedelta(minutes=1))

    def test_preserves_existing_embedding_when_signal_drops(self):
        original_embedding = create_mock_embedding(seed=99, dimensions=EMBEDDING_DIM)
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=original_embedding,
            last_computed_at=timezone.now() - timedelta(days=1),
            interaction_count_at_last_compute=10,
        )
        # No new interactions; profile has nothing for the engine to consume.
        result = update_profile_preference_embedding_task(self.profile.id)

        self.assertTrue(result["skipped"])
        pref = ProfilePreferenceEmbedding.objects.get(profile=self.profile)
        self.assertIsNotNone(pref.embedding)
        # Vector preserved (we didn't blank it).
        import numpy as np

        np.testing.assert_array_almost_equal(
            np.asarray(pref.embedding), np.asarray(original_embedding)
        )

    def test_handles_missing_profile_gracefully(self):
        result = update_profile_preference_embedding_task(999_999)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "profile_not_found")


class StaleSweepTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        _set_post_embedding(
            self.post_5, create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        )
        # Profile_3 has activity in the last 24h; profile_4 has none.
        PostInteraction.objects.create(
            profile=self.profile_3, post=self.post_5, interaction_type=IT.SAVE
        )

    def test_picks_profile_with_recent_activity_and_no_embedding_row(self):
        result = update_stale_preference_embeddings_task()
        self.assertEqual(result["queued"], 1)
        # Eager mode: the per-profile task ran inline, persisting a row.
        self.assertTrue(
            ProfilePreferenceEmbedding.objects.filter(profile=self.profile_3).exists()
        )

    def test_skips_profile_with_fresh_embedding(self):
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile_3,
            embedding=create_mock_embedding(seed=2, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now(),  # very fresh
            interaction_count_at_last_compute=1,
        )
        result = update_stale_preference_embeddings_task()
        self.assertEqual(result["queued"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_picks_profile_with_stale_embedding(self):
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile_3,
            embedding=create_mock_embedding(seed=2, dimensions=EMBEDDING_DIM),
            last_computed_at=timezone.now()
            - timedelta(hours=12),  # past 6h staleness threshold
            interaction_count_at_last_compute=1,
        )
        result = update_stale_preference_embeddings_task()
        self.assertEqual(result["queued"], 1)


class NightlyRefreshTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        _set_post_embedding(
            self.post_5, create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        )
        # Profile_3 interacted 3 days ago: outside the 24h sweep window but inside the 7d safety window.
        obj = PostInteraction.objects.create(
            profile=self.profile_3, post=self.post_5, interaction_type=IT.SAVE
        )
        PostInteraction.objects.filter(pk=obj.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )

    def test_safety_net_includes_recently_inactive_profiles(self):
        result = nightly_preference_embedding_refresh_task()
        self.assertEqual(result["queued"], 1)

    def test_ignores_profiles_with_no_activity_in_seven_days(self):
        PostInteraction.objects.filter(profile=self.profile_3).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        result = nightly_preference_embedding_refresh_task()
        self.assertEqual(result["queued"], 0)

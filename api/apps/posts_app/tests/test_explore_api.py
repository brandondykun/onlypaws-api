"""
Tests for the personalised Explore API.
"""

from django.utils import timezone
from rest_framework import status

from .util import get_explore_posts_url
from apps.interactions_app.models import PostInteraction
from apps.moderation_app.models import PostReport
from apps.posts_app.models import Post
from apps.recommendations_app.models import ProfilePreferenceEmbedding
from apps.recommendations_app.services import EMBEDDING_DIM, EMBEDDING_MODEL
from core.test_utils.helper_classes import BaseFixtureTestCase
from core.test_utils.utils import create_mock_embedding


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


class PrivateExploreApiTests(BaseFixtureTestCase):
    """Authenticated tests for the personalised explore feed."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        # Seed embeddings on the eligible posts so similarity search has something to work with.
        cluster = create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        _set_post_embedding(self.post_5, cluster)
        _set_post_embedding(self.post_6, cluster)
        _set_post_embedding(self.post_7, cluster)
        _set_post_embedding(self.post_8, cluster)

        # Give self.profile a preference embedding so we exercise the
        # similarity path rather than the popularity fallback.
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=cluster,
            last_computed_at=timezone.now(),
            embedding_model=EMBEDDING_MODEL,
            interaction_count_at_last_compute=300,
        )

    def test_returns_only_eligible_posts(self):
        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Eligible: posts from profile_3 (5,6) and profile_4 (7,8).
        # Excluded: own (1,2), followed profile_2 (3,4), reported (1,4).
        eligible_ids = {self.post_5.id, self.post_6.id, self.post_7.id, self.post_8.id}
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertTrue(returned_ids.issubset(eligible_ids))

        # And specifically the ineligible posts must not appear.
        ineligible_ids = {
            self.post_1.id,
            self.post_2.id,
            self.post_3.id,
            self.post_4.id,
        }
        self.assertFalse(returned_ids & ineligible_ids)

    def test_response_shape_has_cursor_fields(self):
        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for key in ("next", "previous", "results", "source"):
            self.assertIn(key, res.data)

    def test_cursor_pagination_advances(self):
        # Page size in tests is small (PAGE_SIZE=24 prod, but only 4 eligible
        # posts in the fixture). On the first page we should consume the
        # entire batch and the next cursor should still be returned (advancing
        # to the next batch_id, which will be empty on the next call).
        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res.data["results"]), 0)
        self.assertIsNotNone(res.data["next"])

        # Follow the cursor — the next batch should be empty.
        cursor_url = res.data["next"]
        res2 = self.client.get(cursor_url)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["results"], [])

    def test_invalid_cursor_returns_404(self):
        url = get_explore_posts_url() + "?cursor=not-a-real-cursor"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_inappropriate_reported_post_is_excluded_from_vector_path(self):
        # Report post_5 (an explore-eligible post on profile_3) for inappropriate
        # content. The vector path should drop it even though its embedding
        # matches the profile's preference.
        PostReport.objects.create(
            post=self.post_5, reporter=self.user_4, reason=self.reason1
        )
        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertNotIn(self.post_5.id, returned_ids)


class ColdStartExploreApiTests(BaseFixtureTestCase):
    """Cold-start users (no preference embedding, no interactions) get popularity fallback."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        # Set posts to READY but DO NOT add embeddings or PostInteractions
        # for self.profile -> the engine should fall back to popularity (and,
        # since the popularity Redis set is empty in this test, ultimately to
        # recency).
        for post in (self.post_5, self.post_6, self.post_7, self.post_8):
            post.status = Post.Status.READY
            post.save(update_fields=["status"])

    def test_cold_start_returns_results_via_popularity_fallback(self):
        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["source"], "popularity")
        # We should still get something back via the recency safety net.
        self.assertGreater(len(res.data["results"]), 0)

    def test_inappropriate_reported_post_is_excluded_from_recency_fallback(self):
        # With Redis empty the engine falls through to the recency safety net.
        # Reported posts must not leak through this last-resort path.
        PostReport.objects.create(
            post=self.post_5, reporter=self.user_4, reason=self.reason1
        )
        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["source"], "popularity")
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertNotIn(self.post_5.id, returned_ids)


class PopularityRevalidationReportTests(BaseFixtureTestCase):
    """
    The popularity Redis set is refreshed every 30 min. A post reported as
    inappropriate between refreshes must not leak into Explore via the cached
    candidate list — the request-path revalidation has to re-apply the filter.
    """

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        for post in (self.post_5, self.post_6, self.post_7, self.post_8):
            post.status = Post.Status.READY
            post.save(update_fields=["status"])

    def test_reported_post_in_popularity_set_is_filtered_at_request_time(self):
        from apps.recommendations_app.popularity import (
            POPULARITY_KEY,
            _redis_client,
        )

        # Seed Redis directly to simulate a stale popularity set that still
        # references post_5 from before it was reported.
        client = _redis_client()
        client.delete(POPULARITY_KEY)
        client.zadd(
            POPULARITY_KEY,
            {
                self.post_5.id: 100.0,
                self.post_6.id: 90.0,
                self.post_7.id: 80.0,
                self.post_8.id: 70.0,
            },
        )
        self.addCleanup(client.delete, POPULARITY_KEY)

        # Report post_5 *after* the popularity set was built.
        PostReport.objects.create(
            post=self.post_5, reporter=self.user_4, reason=self.reason1
        )

        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["source"], "popularity")
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertNotIn(self.post_5.id, returned_ids)
        # The other popularity entries should still come through.
        self.assertTrue(
            returned_ids
            & {self.post_6.id, self.post_7.id, self.post_8.id}
        )


class VectorTopupExploreApiTests(BaseFixtureTestCase):
    """
    When the vector path returns 0 (or fewer than BATCH_SIZE) eligible
    candidates, the engine should top up from popularity instead of
    dead-ending infinite scroll. Heavy follow lists, large seen sets, or
    sparse-niche embeddings can all trigger this in production.
    """

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        for post in (self.post_5, self.post_6, self.post_7, self.post_8):
            post.status = Post.Status.READY
            post.save(update_fields=["status"])

        # Profile has a preference embedding (vector path will run) but no
        # eligible Post has a matching combined_embedding, so the vector
        # query returns zero candidates.
        cluster = create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        ProfilePreferenceEmbedding.objects.create(
            profile=self.profile,
            embedding=cluster,
            last_computed_at=timezone.now(),
            embedding_model=EMBEDDING_MODEL,
            interaction_count_at_last_compute=300,
        )

    def test_empty_vector_falls_through_to_popularity(self):
        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # No vector candidates were produced, so the entire batch came from
        # the popularity topup.
        self.assertEqual(res.data["source"], "popularity")
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertGreater(len(returned_ids), 0)
        # All eligible-for-explore posts (5-8) should be available via topup.
        self.assertTrue(
            returned_ids
            & {self.post_5.id, self.post_6.id, self.post_7.id, self.post_8.id}
        )

    def test_topup_excludes_followed_and_own_posts(self):
        # Followed (profile_2: 3, 4) and own (profile: 1, 2) posts must not
        # leak in via the topup, even though the popularity/recency fallback
        # alone wouldn't filter followed profiles.
        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {p["id"] for p in res.data["results"]}
        for ineligible_id in (
            self.post_1.id,
            self.post_2.id,
            self.post_3.id,
            self.post_4.id,
        ):
            self.assertNotIn(ineligible_id, returned_ids)

    def test_partial_vector_is_topped_up_with_popularity(self):
        # Embed only post_5 so the vector path returns a single result, well
        # below BATCH_SIZE. The remaining capacity should be filled from
        # popularity, and the source label should record both contributions.
        cluster = create_mock_embedding(seed=1, dimensions=EMBEDDING_DIM)
        _set_post_embedding(self.post_5, cluster)

        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertIn(self.post_5.id, returned_ids)
        self.assertTrue(
            returned_ids & {self.post_6.id, self.post_7.id, self.post_8.id}
        )
        self.assertTrue(res.data["source"].endswith("+popularity"))

    def test_topup_from_popularity_set_excludes_followed_profile(self):
        # Seed Redis with all eight posts so the request-time validation
        # branch (rather than recency) supplies the topup. Followed-profile
        # posts (post_3, post_4) must still be filtered out via the
        # excluded_profile_ids the topup passes through.
        from apps.recommendations_app.popularity import (
            POPULARITY_KEY,
            _redis_client,
        )

        client = _redis_client()
        client.delete(POPULARITY_KEY)
        client.zadd(
            POPULARITY_KEY,
            {
                self.post_3.id: 100.0,
                self.post_4.id: 95.0,
                self.post_5.id: 90.0,
                self.post_6.id: 85.0,
                self.post_7.id: 80.0,
                self.post_8.id: 75.0,
            },
        )
        self.addCleanup(client.delete, POPULARITY_KEY)

        res = self.client.get(get_explore_posts_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {p["id"] for p in res.data["results"]}
        self.assertNotIn(self.post_3.id, returned_ids)
        self.assertNotIn(self.post_4.id, returned_ids)


class PublicExploreApiTests(BaseFixtureTestCase):
    """Unauthenticated requests are rejected."""

    def test_unauthenticated_request_returns_401(self):
        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

"""
Tests for the PostInteraction api (CreatePostInteractionView).
"""

from rest_framework import status

from apps.interactions_app.models import PostInteraction
from apps.moderation_app.models import Block
from core.test_utils.helper_classes import BaseFixtureTestCase

from .util import create_post_interaction_url


class PublicPostInteractionApiTests(BaseFixtureTestCase):
    """Test the public (unauthenticated) features of the PostInteraction API."""

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests must be rejected and write nothing."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(PostInteraction.objects.count(), 0)


class PrivatePostInteractionApiTests(BaseFixtureTestCase):
    """Test the private (authenticated) features of the PostInteraction API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # Authenticate as self.profile (profile_1).
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    # ------------------------------------------------------------------
    # Post resolution
    # ------------------------------------------------------------------

    def test_non_existent_post_returns_404(self):
        """Recording an interaction for a missing post returns 404."""
        url = create_post_interaction_url(99999)
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(PostInteraction.objects.count(), 0)

    # ------------------------------------------------------------------
    # Happy path: each interaction type
    # ------------------------------------------------------------------

    def test_create_preview_click_interaction(self):
        """A preview_click interaction is recorded with the auth profile and target post."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.count(), 1)

        pi = PostInteraction.objects.first()
        self.assertEqual(pi.profile_id, self.profile.id)
        self.assertEqual(pi.post_id, self.post_3.id)
        self.assertEqual(pi.interaction_type, "preview_click")
        self.assertIsNone(pi.dwell_time_ms)
        self.assertTrue(pi.public_id)
        self.assertIsNotNone(pi.created_at)

    def test_create_like_interaction(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(url, {"interaction_type": "like"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.first().interaction_type, "like")

    def test_create_save_interaction(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(url, {"interaction_type": "save"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.first().interaction_type, "save")

    def test_create_comment_interaction(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(url, {"interaction_type": "comment"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.first().interaction_type, "comment")

    def test_create_view_interaction_without_dwell_time(self):
        """A view interaction may omit dwell_time_ms — it stays null."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(url, {"interaction_type": "view"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pi = PostInteraction.objects.first()
        self.assertEqual(pi.interaction_type, "view")
        self.assertIsNone(pi.dwell_time_ms)

    def test_create_view_interaction_with_dwell_time(self):
        """A view interaction with a positive dwell value persists that value."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {"interaction_type": "view", "dwell_time_ms": 4200},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pi = PostInteraction.objects.first()
        self.assertEqual(pi.interaction_type, "view")
        self.assertEqual(pi.dwell_time_ms, 4200)

    def test_create_view_interaction_with_zero_dwell_time(self):
        """0 ms is a valid dwell value (MinValueValidator(0))."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {"interaction_type": "view", "dwell_time_ms": 0},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.first().dwell_time_ms, 0)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_missing_interaction_type_returns_400(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("interaction_type", res.data)
        self.assertEqual(PostInteraction.objects.count(), 0)

    def test_invalid_interaction_type_returns_400(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url, {"interaction_type": "not_a_real_type"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("interaction_type", res.data)
        self.assertEqual(PostInteraction.objects.count(), 0)

    def test_dwell_time_with_non_view_type_returns_400(self):
        """dwell_time_ms is only valid for 'view'; any other type is rejected."""
        url = create_post_interaction_url(self.post_3.id)
        for non_view_type in ["preview_click", "like", "save", "comment"]:
            with self.subTest(interaction_type=non_view_type):
                res = self.client.post(
                    url,
                    {"interaction_type": non_view_type, "dwell_time_ms": 1000},
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("dwell_time_ms", res.data)
        self.assertEqual(PostInteraction.objects.count(), 0)

    def test_negative_dwell_time_returns_400(self):
        """Negative dwell values violate PositiveIntegerField + MinValueValidator(0)."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {"interaction_type": "view", "dwell_time_ms": -100},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PostInteraction.objects.count(), 0)

    # ------------------------------------------------------------------
    # Profile is taken from auth context, not the body
    # ------------------------------------------------------------------

    def test_profile_in_body_is_ignored_in_favor_of_auth_profile(self):
        """Even if a body specifies a different profile, the server records the auth profile."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {
                "interaction_type": "preview_click",
                "profile": self.profile_2.id,  # spoof attempt
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pi = PostInteraction.objects.first()
        self.assertEqual(pi.profile_id, self.profile.id)

    def test_post_in_body_is_ignored_in_favor_of_url_post(self):
        """Even if the body specifies a different post, the server records the URL's post."""
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {
                "interaction_type": "preview_click",
                "post": self.post_4.id,  # spoof attempt
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pi = PostInteraction.objects.first()
        self.assertEqual(pi.post_id, self.post_3.id)

    # ------------------------------------------------------------------
    # Append-only event log: same tuple may appear many times
    # ------------------------------------------------------------------

    def test_repeated_interactions_create_separate_rows(self):
        """The model is an event log; the same (profile, post, type) tuple is allowed to repeat."""
        url = create_post_interaction_url(self.post_3.id)
        for _ in range(3):
            res = self.client.post(
                url, {"interaction_type": "preview_click"}, format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.assertEqual(
            PostInteraction.objects.filter(
                profile=self.profile,
                post=self.post_3,
                interaction_type="preview_click",
            ).count(),
            3,
        )

    def test_different_interaction_types_for_same_post_all_persist(self):
        url = create_post_interaction_url(self.post_3.id)
        for itype in ["preview_click", "view", "like", "save", "comment"]:
            res = self.client.post(url, {"interaction_type": itype}, format="json")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            PostInteraction.objects.filter(
                profile=self.profile, post=self.post_3
            ).count(),
            5,
        )

    # ------------------------------------------------------------------
    # Privacy: private profile gating
    # ------------------------------------------------------------------

    def test_private_post_owner_blocks_non_follower(self):
        """Non-follower cannot record interaction on a private profile's post."""
        # self.profile does NOT follow self.profile_3 in the fixture.
        self.profile_3.is_private = True
        self.profile_3.save(update_fields=["is_private"])

        url = create_post_interaction_url(self.post_5.id)  # belongs to profile_3
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(PostInteraction.objects.count(), 0)

    def test_private_post_owner_allows_follower(self):
        """Follower can record interaction on a private profile's post."""
        # self.profile DOES follow self.profile_2 (per fixture).
        self.profile_2.is_private = True
        self.profile_2.save(update_fields=["is_private"])

        url = create_post_interaction_url(self.post_3.id)  # belongs to profile_2
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.count(), 1)

    def test_owner_can_interact_with_own_private_post(self):
        """A profile can always record interactions on their own posts, even if private."""
        self.profile.is_private = True
        self.profile.save(update_fields=["is_private"])

        url = create_post_interaction_url(self.post_1.id)  # belongs to self.profile
        res = self.client.post(
            url,
            {"interaction_type": "view", "dwell_time_ms": 1500},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostInteraction.objects.count(), 1)

    # ------------------------------------------------------------------
    # Blocking: rejected in either direction
    # ------------------------------------------------------------------

    def test_blocked_by_post_owner_returns_403(self):
        """If the post owner has blocked the requester, the interaction is rejected."""
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        url = create_post_interaction_url(self.post_5.id)  # belongs to profile_3
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(PostInteraction.objects.count(), 0)

    def test_blocking_post_owner_returns_403(self):
        """If the requester has blocked the post owner, the interaction is rejected."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        url = create_post_interaction_url(self.post_5.id)  # belongs to profile_3
        res = self.client.post(
            url, {"interaction_type": "preview_click"}, format="json"
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(PostInteraction.objects.count(), 0)

    # ------------------------------------------------------------------
    # Response shape
    # ------------------------------------------------------------------

    def test_response_contains_expected_fields(self):
        url = create_post_interaction_url(self.post_3.id)
        res = self.client.post(
            url,
            {"interaction_type": "view", "dwell_time_ms": 2500},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        for field in (
            "id",
            "public_id",
            "post",
            "profile",
            "interaction_type",
            "dwell_time_ms",
            "created_at",
        ):
            self.assertIn(field, res.data)
        self.assertEqual(res.data["post"], self.post_3.id)
        self.assertEqual(res.data["profile"], self.profile.id)
        self.assertEqual(res.data["interaction_type"], "view")
        self.assertEqual(res.data["dwell_time_ms"], 2500)
        self.assertTrue(res.data["public_id"])

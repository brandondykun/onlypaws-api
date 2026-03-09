"""
Tests for the Block API endpoints.
"""

from rest_framework import status

from apps.moderation_app.models import Block
from apps.interactions_app.models import Follow, FollowRequest
from apps.notifications_app.models import Notification, NotificationType
from .util import BLOCK_PROFILE_URL, LIST_BLOCKED_PROFILES_URL, unblock_profile_url
from core.test_utils.utils import create_user, create_profile, create_follow
from core.test_utils.helper_classes import BaseFixtureTestCase


# ==================== BLOCK PROFILE TESTS ====================


class PrivateBlockProfileApiTests(BaseFixtureTestCase):
    """Test the private features of the Block Profile API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_block_profile_successful(self):
        """Test blocking a profile returns 201 and creates the block."""
        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["blocked_public_id"], str(self.profile_3.public_id))
        self.assertEqual(res.data["blocked_username"], self.profile_3.username)
        self.assertTrue(
            Block.objects.filter(blocker=self.profile, blocked=self.profile_3).exists()
        )

    def test_block_profile_removes_outgoing_follow(self):
        """Test blocking a profile removes the follow from blocker to blocked."""
        # self.profile already follows profile_2 (from setUp)
        self.assertTrue(
            Follow.objects.filter(
                followed_by=self.profile, followed=self.profile_2
            ).exists()
        )

        data = {"profile_id": str(self.profile_2.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Follow.objects.filter(
                followed_by=self.profile, followed=self.profile_2
            ).exists()
        )

    def test_block_profile_removes_incoming_follow(self):
        """Test blocking a profile removes the follow from blocked to blocker."""
        create_follow(self.profile_3, self.profile)
        self.assertTrue(
            Follow.objects.filter(
                followed_by=self.profile_3, followed=self.profile
            ).exists()
        )

        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Follow.objects.filter(
                followed_by=self.profile_3, followed=self.profile
            ).exists()
        )

    def test_block_profile_removes_follow_requests_both_directions(self):
        """Test blocking removes pending follow requests in both directions."""
        FollowRequest.objects.create(requester=self.profile, target=self.profile_3)
        FollowRequest.objects.create(requester=self.profile_3, target=self.profile)

        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            FollowRequest.objects.filter(
                requester=self.profile, target=self.profile_3
            ).exists()
        )
        self.assertFalse(
            FollowRequest.objects.filter(
                requester=self.profile_3, target=self.profile
            ).exists()
        )

    def test_block_profile_deletes_notifications_both_directions(self):
        """Test blocking deletes notifications between both profiles."""
        Notification.objects.create(
            recipient=self.profile,
            sender=self.profile_3,
            notification_type=NotificationType.LIKE_POST,
            title="They liked your post",
            message="Notification from profile_3",
            post=self.post_1,
        )
        Notification.objects.create(
            recipient=self.profile_3,
            sender=self.profile,
            notification_type=NotificationType.LIKE_POST,
            title="You liked their post",
            message="Notification from profile",
            post=self.post_5,
        )

        data = {"profile_id": str(self.profile_3.public_id)}
        self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.profile, sender=self.profile_3
            ).count(),
            0,
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.profile_3, sender=self.profile
            ).count(),
            0,
        )

    def test_block_self_returns_error(self):
        """Test blocking yourself returns 400."""
        data = {"profile_id": str(self.profile.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Block.objects.filter(blocker=self.profile, blocked=self.profile).exists()
        )

    def test_block_already_blocked_profile_returns_error(self):
        """Test blocking a profile that is already blocked returns 400."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # Should still only have one block
        self.assertEqual(
            Block.objects.filter(blocker=self.profile, blocked=self.profile_3).count(),
            1,
        )

    def test_block_nonexistent_profile_returns_error(self):
        """Test blocking a profile that doesn't exist returns 400."""
        data = {"profile_id": "01HF7YQX8J9K2P3M4N5R6S7T8X"}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_block_profile_without_profile_id_returns_error(self):
        """Test blocking without providing a profile_id returns 400."""
        res = self.client.post(BLOCK_PROFILE_URL, data={})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_block_does_not_affect_unrelated_follows(self):
        """Test that blocking only removes follows between the two profiles."""
        # profile_3 follows profile_2
        create_follow(self.profile_3, self.profile_2)
        starting_follows_count = Follow.objects.count()

        # Block profile_3 (self.profile -> profile_3 has no follow relationship)
        data = {"profile_id": str(self.profile_3.public_id)}
        self.client.post(BLOCK_PROFILE_URL, data=data)

        # profile_3's follow of profile_2 should still exist
        self.assertTrue(
            Follow.objects.filter(
                followed_by=self.profile_3, followed=self.profile_2
            ).exists()
        )

    def test_block_does_not_affect_unrelated_notifications(self):
        """Test that blocking only deletes notifications between the two profiles."""
        # Notification from profile_3 to profile_2 (unrelated)
        notif = Notification.objects.create(
            recipient=self.profile_2,
            sender=self.profile_3,
            notification_type=NotificationType.LIKE_POST,
            title="Unrelated notification",
            message="Should not be deleted",
            post=self.post_3,
        )

        data = {"profile_id": str(self.profile_3.public_id)}
        self.client.post(BLOCK_PROFILE_URL, data=data)

        # Unrelated notification should still exist
        self.assertTrue(Notification.objects.filter(id=notif.id).exists())

    def test_block_response_contains_expected_fields(self):
        """Test that the block response contains all expected fields."""
        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.data)
        self.assertIn("blocked_public_id", res.data)
        self.assertIn("blocked_username", res.data)
        self.assertIn("created_at", res.data)


class PublicBlockProfileApiTests(BaseFixtureTestCase):
    """Test that block profile requires authentication."""

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_block_profile_unauthenticated_returns_error(self):
        """Test blocking a profile without authentication returns 401."""
        data = {"profile_id": str(self.profile_3.public_id)}
        res = self.client.post(BLOCK_PROFILE_URL, data=data)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ==================== UNBLOCK PROFILE TESTS ====================


class PrivateUnblockProfileApiTests(BaseFixtureTestCase):
    """Test the private features of the Unblock Profile API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_unblock_profile_successful(self):
        """Test unblocking a profile returns 204 and removes the block."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        url = unblock_profile_url(str(self.profile_3.public_id))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Block.objects.filter(blocker=self.profile, blocked=self.profile_3).exists()
        )

    def test_unblock_profile_not_blocked_returns_404(self):
        """Test unblocking a profile that is not blocked returns 404."""
        url = unblock_profile_url(str(self.profile_3.public_id))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_unblock_nonexistent_profile_returns_404(self):
        """Test unblocking a nonexistent profile returns 404."""
        url = unblock_profile_url("01HF7YQX8J9K2P3M4N5R6S7T8X")
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_unblock_does_not_remove_reverse_block(self):
        """Test unblocking only removes the block you created, not the reverse."""
        # Both profiles block each other
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        url = unblock_profile_url(str(self.profile_3.public_id))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        # Our block is removed
        self.assertFalse(
            Block.objects.filter(blocker=self.profile, blocked=self.profile_3).exists()
        )
        # Their block on us remains
        self.assertTrue(
            Block.objects.filter(blocker=self.profile_3, blocked=self.profile).exists()
        )

    def test_cannot_unblock_someone_elses_block(self):
        """Test that you can only unblock profiles you have blocked."""
        # profile_3 blocked profile_2, but self.profile tries to unblock
        Block.objects.create(blocker=self.profile_3, blocked=self.profile_2)

        url = unblock_profile_url(str(self.profile_2.public_id))
        res = self.client.delete(url)

        # self.profile hasn't blocked profile_2, so 404
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        # profile_3's block should still exist
        self.assertTrue(
            Block.objects.filter(blocker=self.profile_3, blocked=self.profile_2).exists()
        )


class PublicUnblockProfileApiTests(BaseFixtureTestCase):
    """Test that unblock profile requires authentication."""

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_unblock_profile_unauthenticated_returns_error(self):
        """Test unblocking a profile without authentication returns 401."""
        url = unblock_profile_url(str(self.profile_3.public_id))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ==================== LIST BLOCKED PROFILES TESTS ====================


class PrivateListBlockedProfilesApiTests(BaseFixtureTestCase):
    """Test the private features of the List Blocked Profiles API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_list_blocked_profiles_empty(self):
        """Test listing blocked profiles when none are blocked returns empty list."""
        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_blocked_profiles_returns_blocked_profiles(self):
        """Test listing blocked profiles returns profiles the user has blocked."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

    def test_list_blocked_profiles_does_not_include_blocks_by_others(self):
        """Test listing blocked profiles does not include blocks made by other profiles."""
        # self.profile blocks profile_2
        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        # profile_3 blocks profile_4 (unrelated)
        Block.objects.create(blocker=self.profile_3, blocked=self.profile_4)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)

    def test_list_blocked_profiles_does_not_include_blocked_by(self):
        """Test listing blocked profiles does not include profiles that blocked you."""
        # profile_3 blocks self.profile (reverse direction)
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_blocked_profiles_ordered_by_most_recent(self):
        """Test that blocked profiles are returned with most recently blocked first."""
        block1 = Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        block2 = Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)
        # Most recently blocked (profile_3) should be first
        self.assertEqual(res.data["results"][0]["id"], block2.id)
        self.assertEqual(res.data["results"][1]["id"], block1.id)

    def test_list_blocked_profiles_contains_profile_details(self):
        """Test that blocked profile entries contain profile information."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_2)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)

        entry = res.data["results"][0]
        self.assertIn("id", entry)
        self.assertIn("blocked_profile", entry)
        self.assertIn("created_at", entry)

        blocked_profile = entry["blocked_profile"]
        self.assertIn("username", blocked_profile)
        self.assertIn("public_id", blocked_profile)
        self.assertEqual(blocked_profile["username"], self.profile_2.username)

    def test_list_blocked_profiles_pagination(self):
        """Test that blocked profiles list is paginated."""
        # Create enough blocks to exceed page size (50)
        for i in range(55):
            user = create_user(f"blocktest{i}@example.com", f"password{i}")
            profile = create_profile(f"blocked_user_{i:03d}", user, f"About {i}")
            Block.objects.create(blocker=self.profile, blocked=profile)

        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 50)
        self.assertIsNotNone(res.data["next"])
        self.assertEqual(res.data["count"], 55)


class PublicListBlockedProfilesApiTests(BaseFixtureTestCase):
    """Test that listing blocked profiles requires authentication."""

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_list_blocked_profiles_unauthenticated_returns_error(self):
        """Test listing blocked profiles without authentication returns 401."""
        res = self.client.get(LIST_BLOCKED_PROFILES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ==================== BLOCK INTEGRATION WITH FOLLOW API TESTS ====================


class BlockFollowIntegrationTests(BaseFixtureTestCase):
    """Test that blocking prevents following and vice versa."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_cannot_follow_blocked_profile(self):
        """Test that you cannot follow a profile you have blocked."""
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        from apps.interactions_app.tests.util import create_follow_url

        url = create_follow_url()
        data = {"profileId": str(self.profile_3.public_id)}
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Follow.objects.filter(
                followed_by=self.profile, followed=self.profile_3
            ).exists()
        )

    def test_cannot_follow_profile_that_blocked_you(self):
        """Test that you cannot follow a profile that has blocked you."""
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        from apps.interactions_app.tests.util import create_follow_url

        url = create_follow_url()
        data = {"profileId": str(self.profile_3.public_id)}
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ==================== BLOCK INTEGRATION WITH FEED/EXPLORE TESTS ====================


class BlockFeedExploreIntegrationTests(BaseFixtureTestCase):
    """Test that blocked profiles' posts are excluded from feed and explore."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_blocked_profile_posts_excluded_from_feed(self):
        """Test that posts from a blocked profile are excluded from feed."""
        from apps.posts_app.tests.util import get_feed_url

        # self.profile follows profile_2, feed should have profile_2's posts
        url = get_feed_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        feed_count_before = len(res.data["results"])
        self.assertGreater(feed_count_before, 0)

        # Block profile_2
        Block.objects.create(blocker=self.profile, blocked=self.profile_2)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_blocked_profile_posts_excluded_from_explore(self):
        """Test that posts from a blocked profile are excluded from explore."""
        from apps.posts_app.tests.util import get_explore_posts_url

        url = get_explore_posts_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        explore_count_before = len(res.data["results"])

        # Block profile_3 (not followed, shows in explore)
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        explore_count_after = len(res.data["results"])

        # Should have fewer posts (profile_3's posts excluded)
        self.assertLess(explore_count_after, explore_count_before)

    def test_profile_that_blocked_you_posts_excluded_from_explore(self):
        """Test that posts from a profile that blocked you are excluded from explore."""
        from apps.posts_app.tests.util import get_explore_posts_url

        url = get_explore_posts_url()
        res = self.client.get(url)
        explore_count_before = len(res.data["results"])

        # profile_3 blocks self.profile (reverse direction)
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        res = self.client.get(url)
        explore_count_after = len(res.data["results"])

        self.assertLess(explore_count_after, explore_count_before)


# ==================== BLOCK INTEGRATION WITH FOLLOWERS/FOLLOWING TESTS ====================


class BlockFollowersFollowingIntegrationTests(BaseFixtureTestCase):
    """Test that blocked profiles are excluded from followers/following lists."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_blocked_profile_excluded_from_followers_list(self):
        """Test that a blocked profile is excluded from the followers list."""
        from apps.interactions_app.tests.util import list_followers_url

        # profile_3 follows profile_2
        create_follow(self.profile_3, self.profile_2)
        # profile_4 follows profile_2
        create_follow(self.profile_4, self.profile_2)

        # self.profile blocks profile_3
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        url = list_followers_url(str(self.profile_2.public_id))
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        follower_ids = [f["id"] for f in res.data["results"]]
        # profile_3 should be excluded
        self.assertNotIn(self.profile_3.id, follower_ids)
        # profile_4 and self.profile should still be visible
        self.assertIn(self.profile_4.id, follower_ids)
        self.assertIn(self.profile.id, follower_ids)

    def test_blocked_profile_excluded_from_following_list(self):
        """Test that a blocked profile is excluded from the following list."""
        from apps.interactions_app.tests.util import list_following_url

        # profile_2 follows multiple profiles
        create_follow(self.profile_2, self.profile_3)
        create_follow(self.profile_2, self.profile_4)

        # self.profile blocks profile_3
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        url = list_following_url(str(self.profile_2.public_id))
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        following_ids = [f["id"] for f in res.data["results"]]
        # profile_3 should be excluded
        self.assertNotIn(self.profile_3.id, following_ids)
        # profile_4 should still be visible
        self.assertIn(self.profile_4.id, following_ids)


# ==================== BLOCK INTEGRATION WITH COMMENTS TESTS ====================


class BlockCommentsIntegrationTests(BaseFixtureTestCase):
    """Test that comments from blocked profiles are excluded."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_blocked_profile_comments_excluded_from_post(self):
        """Test that comments from a blocked profile are excluded from comment list."""
        from apps.interactions_app.tests.util import list_post_comments_url
        from core.test_utils.utils import create_comment

        # profile_3 comments on post_1
        create_comment(self.profile_3, "Comment from profile_3", self.post_1)

        url = list_post_comments_url(self.post_1.id)

        # Before blocking, profile_3's comment should be visible
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        comment_count_before = len(res.data["results"])

        # Block profile_3
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        # After blocking, profile_3's comment should be excluded
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        comment_count_after = len(res.data["results"])

        self.assertLess(comment_count_after, comment_count_before)


# ==================== BLOCK INTEGRATION WITH SEARCH TESTS ====================


class BlockSearchIntegrationTests(BaseFixtureTestCase):
    """Test that blocked profiles are excluded from search results."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_blocked_profile_excluded_from_search(self):
        """Test that a blocked profile is excluded from search results."""
        from apps.profile_app.tests.util import search_profiles_url

        # Search for "username" - should find profile_2, profile_3, profile_4
        url = search_profiles_url("username")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        search_count_before = len(res.data["results"])

        # Block profile_2
        Block.objects.create(blocker=self.profile, blocked=self.profile_2)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        search_count_after = len(res.data["results"])

        self.assertEqual(search_count_after, search_count_before - 1)

        result_usernames = [p["username"] for p in res.data["results"]]
        self.assertNotIn(self.profile_2.username, result_usernames)

    def test_profile_that_blocked_you_excluded_from_search(self):
        """Test that a profile that blocked you is excluded from search."""
        from apps.profile_app.tests.util import search_profiles_url

        url = search_profiles_url("username")
        res = self.client.get(url)
        search_count_before = len(res.data["results"])

        # profile_3 blocks self.profile
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)

        res = self.client.get(url)
        search_count_after = len(res.data["results"])

        self.assertEqual(search_count_after, search_count_before - 1)


# ==================== BLOCK INTEGRATION WITH NOTIFICATIONS TESTS ====================


class BlockNotificationsIntegrationTests(BaseFixtureTestCase):
    """Test that notifications from blocked profiles are excluded."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_blocked_profile_notifications_excluded(self):
        """Test that notifications from a blocked sender are excluded from listing."""
        from apps.notifications_app.tests.util import NOTIFICATIONS_LIST_URL

        # Create notifications from different senders
        Notification.objects.create(
            recipient=self.profile,
            sender=self.profile_2,
            notification_type=NotificationType.LIKE_POST,
            title="Notification from profile_2",
            message="Should remain visible",
            post=self.post_1,
        )
        Notification.objects.create(
            recipient=self.profile,
            sender=self.profile_3,
            notification_type=NotificationType.LIKE_POST,
            title="Notification from profile_3",
            message="Should be hidden after block",
            post=self.post_1,
        )

        # Before blocking, both notifications visible
        res = self.client.get(NOTIFICATIONS_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        # Block profile_3
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        # After blocking, only profile_2's notification visible
        res = self.client.get(NOTIFICATIONS_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(
            res.data["results"][0]["title"], "Notification from profile_2"
        )


# ==================== BLOCK INTEGRATION WITH SAVED POSTS TESTS ====================


class BlockSavedPostsIntegrationTests(BaseFixtureTestCase):
    """Test that saved posts from blocked profiles are excluded."""

    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_saved_post_from_blocked_profile_excluded(self):
        """Test that saved posts from blocked profiles are not listed."""
        from apps.posts_app.models import SavedPost
        from apps.posts_app.tests.util import list_create_saved_post_url

        # Save posts from profile_2 and profile_3
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        SavedPost.objects.create(profile=self.profile, post=self.post_5)

        url = list_create_saved_post_url()
        res = self.client.get(url)
        self.assertEqual(len(res.data["results"]), 2)

        # Block profile_3 (who owns post_5)
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)

        res = self.client.get(url)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["id"], self.post_3.id)


# ==================== BLOCK UTILITY FUNCTION TESTS ====================


class BlockUtilityTests(BaseFixtureTestCase):
    """Test the block utility functions."""

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_get_blocked_profile_ids_empty(self):
        """Test get_blocked_profile_ids returns empty set when no blocks exist."""
        from apps.moderation_app.block_utils import get_blocked_profile_ids

        result = get_blocked_profile_ids(self.profile)
        self.assertEqual(result, set())

    def test_get_blocked_profile_ids_outgoing(self):
        """Test get_blocked_profile_ids includes profiles we blocked."""
        from apps.moderation_app.block_utils import get_blocked_profile_ids

        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        result = get_blocked_profile_ids(self.profile)
        self.assertIn(self.profile_2.id, result)

    def test_get_blocked_profile_ids_incoming(self):
        """Test get_blocked_profile_ids includes profiles that blocked us."""
        from apps.moderation_app.block_utils import get_blocked_profile_ids

        Block.objects.create(blocker=self.profile_3, blocked=self.profile)
        result = get_blocked_profile_ids(self.profile)
        self.assertIn(self.profile_3.id, result)

    def test_get_blocked_profile_ids_both_directions(self):
        """Test get_blocked_profile_ids includes both directions."""
        from apps.moderation_app.block_utils import get_blocked_profile_ids

        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        Block.objects.create(blocker=self.profile_3, blocked=self.profile)
        result = get_blocked_profile_ids(self.profile)
        self.assertIn(self.profile_2.id, result)
        self.assertIn(self.profile_3.id, result)
        self.assertNotIn(self.profile.id, result)

    def test_get_blocked_profile_ids_caches_result(self):
        """Test that get_blocked_profile_ids caches result on profile instance."""
        from apps.moderation_app.block_utils import get_blocked_profile_ids

        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        result1 = get_blocked_profile_ids(self.profile)
        self.assertTrue(hasattr(self.profile, "_blocked_profile_ids_cache"))

        # Add another block - cache should return stale data (by design)
        Block.objects.create(blocker=self.profile, blocked=self.profile_3)
        result2 = get_blocked_profile_ids(self.profile)

        # Should be the same object (cached)
        self.assertIs(result1, result2)
        # profile_3 should NOT be in cached result
        self.assertNotIn(self.profile_3.id, result2)

    def test_are_profiles_blocking_true(self):
        """Test are_profiles_blocking returns True when block exists."""
        from apps.moderation_app.block_utils import are_profiles_blocking

        Block.objects.create(blocker=self.profile, blocked=self.profile_2)
        self.assertTrue(are_profiles_blocking(self.profile, self.profile_2))
        # Should work in reverse direction too
        self.assertTrue(are_profiles_blocking(self.profile_2, self.profile))

    def test_are_profiles_blocking_false(self):
        """Test are_profiles_blocking returns False when no block exists."""
        from apps.moderation_app.block_utils import are_profiles_blocking

        self.assertFalse(are_profiles_blocking(self.profile, self.profile_2))

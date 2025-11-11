"""
Tests for the ListFollowersView and ListFollowingView API endpoints.
"""

from rest_framework import status

from .util import list_followers_url, list_following_url
from core.test_utils.utils import create_user, create_profile, create_follow
from core.test_utils.helper_classes import BaseFixtureTestCase


class PrivateListFollowersApiTests(BaseFixtureTestCase):
    """Test the private features of the ListFollowersView API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_list_followers_successful(self):
        """Test listing followers for a profile returns correct profiles."""
        # Create additional follow relationships
        # profile_3 follows profile_2
        create_follow(self.profile_3, self.profile_2)
        # profile_4 follows profile_2
        create_follow(self.profile_4, self.profile_2)

        # profile_2 now has 3 followers: self.profile, profile_3, profile_4
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 3)

        # Verify the followers are in the correct order (alphabetically by username)
        follower_ids = [follower["id"] for follower in res.data["results"]]
        self.assertIn(self.profile.id, follower_ids)
        self.assertIn(self.profile_3.id, follower_ids)
        self.assertIn(self.profile_4.id, follower_ids)

        # Verify alphabetical order by username
        usernames = [follower["username"] for follower in res.data["results"]]
        self.assertEqual(usernames, sorted(usernames))

    def test_list_followers_empty_when_no_followers(self):
        """Test listing followers for a profile with no followers returns empty list."""
        # profile_3 has no followers
        url = list_followers_url(self.profile_3.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_followers_with_username_filter_successful(self):
        """Test listing followers with username filter returns matching profiles."""
        # Create profiles with specific usernames
        user_5 = create_user("test5@example.com", "user5-password-123")
        profile_5 = create_profile("alice_smith", user_5, "About alice.")
        user_6 = create_user("test6@example.com", "user6-password-123")
        profile_6 = create_profile("alice_jones", user_6, "About alice j.")
        user_7 = create_user("test7@example.com", "user7-password-123")
        profile_7 = create_profile("bob_williams", user_7, "About bob.")

        # All three follow profile_2
        create_follow(profile_5, self.profile_2)
        create_follow(profile_6, self.profile_2)
        create_follow(profile_7, self.profile_2)

        # Filter by "alice" - should return alice_smith and alice_jones
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url, {"username": "alice"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        usernames = [follower["username"] for follower in res.data["results"]]
        self.assertIn("alice_smith", usernames)
        self.assertIn("alice_jones", usernames)
        self.assertNotIn("bob_williams", usernames)

    def test_list_followers_with_username_filter_case_insensitive(self):
        """Test listing followers with username filter is case insensitive."""
        user_5 = create_user("test5@example.com", "user5-password-123")
        profile_5 = create_profile("AliceSmith", user_5, "About alice.")

        create_follow(profile_5, self.profile_2)

        # Filter with lowercase "alice" should still match "AliceSmith"
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url, {"username": "alice"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["username"], "AliceSmith")

    def test_list_followers_with_username_filter_no_matches(self):
        """Test listing followers with username filter that matches nothing returns empty."""
        create_follow(self.profile_3, self.profile_2)

        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url, {"username": "nonexistent"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_followers_nonexistent_profile_returns_empty(self):
        """Test listing followers for nonexistent profile returns empty list."""
        url = list_followers_url(99999)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_followers_pagination_works(self):
        """Test that followers list is paginated correctly."""
        # Create 20 profiles that follow profile_2 (more than page_size of 15)
        for i in range(20):
            user = create_user(f"test{i+10}@example.com", f"password{i+10}")
            profile = create_profile(f"user_{i+10:02d}", user, f"About user {i+10}")
            create_follow(profile, self.profile_2)

        # profile_2 now has 21 followers (20 new + self.profile)
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # First page should have 15 results (page_size)
        self.assertEqual(len(res.data["results"]), 15)
        # Check pagination metadata
        self.assertIsNotNone(res.data["next"])
        self.assertIsNone(res.data["previous"])
        self.assertEqual(res.data["count"], 21)

    def test_list_followers_pagination_second_page(self):
        """Test that second page of followers list returns remaining results."""
        # Create 20 profiles that follow profile_2
        for i in range(20):
            user = create_user(f"test{i+10}@example.com", f"password{i+10}")
            profile = create_profile(f"user_{i+10:02d}", user, f"About user {i+10}")
            create_follow(profile, self.profile_2)

        # Get second page
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url, {"page": 2})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Second page should have 6 results (21 total - 15 on first page)
        self.assertEqual(len(res.data["results"]), 6)
        self.assertIsNone(res.data["next"])
        self.assertIsNotNone(res.data["previous"])

    def test_list_followers_includes_profile_details(self):
        """Test that followers list includes full profile details."""
        create_follow(self.profile_3, self.profile_2)

        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res.data["results"]), 0)

        # Check that profile details are included
        follower = res.data["results"][0]
        self.assertIn("id", follower)
        self.assertIn("username", follower)
        self.assertIn("about", follower)


class PublicListFollowersApiTests(BaseFixtureTestCase):
    """Test the public features of the ListFollowersView API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_list_followers_without_authentication_returns_error(self):
        """Test listing followers without authentication returns 401."""
        url = list_followers_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateListFollowingApiTests(BaseFixtureTestCase):
    """Test the private features of the ListFollowingView API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_list_following_successful(self):
        """Test listing profiles that a profile follows returns correct profiles."""
        # self.profile follows profile_2 (from setUp)
        # Add more follows
        create_follow(self.profile, self.profile_3)
        create_follow(self.profile, self.profile_4)

        # self.profile now follows 3 profiles: profile_2, profile_3, profile_4
        url = list_following_url(self.profile.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 3)

        # Verify the following profiles are in the correct order (alphabetically by username)
        following_ids = [profile["id"] for profile in res.data["results"]]
        self.assertIn(self.profile_2.id, following_ids)
        self.assertIn(self.profile_3.id, following_ids)
        self.assertIn(self.profile_4.id, following_ids)

        # Verify alphabetical order by username
        usernames = [profile["username"] for profile in res.data["results"]]
        self.assertEqual(usernames, sorted(usernames))

    def test_list_following_empty_when_not_following_anyone(self):
        """Test listing following for a profile that follows no one returns empty list."""
        # profile_3 doesn't follow anyone
        url = list_following_url(self.profile_3.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_following_with_username_filter_successful(self):
        """Test listing following with username filter returns matching profiles."""
        # Create profiles with specific usernames
        user_5 = create_user("test5@example.com", "user5-password-123")
        profile_5 = create_profile("charlie_smith", user_5,"About charlie.")
        user_6 = create_user("test6@example.com", "user6-password-123")
        profile_6 = create_profile("charlie_jones", user_6, "About charlie j.")
        user_7 = create_user("test7@example.com", "user7-password-123")
        profile_7 = create_profile("david_williams", user_7, "About david.")

        # profile_2 follows all three
        create_follow(self.profile_2, profile_5)
        create_follow(self.profile_2, profile_6)
        create_follow(self.profile_2, profile_7)

        # Filter by "charlie" - should return charlie_smith and charlie_jones
        url = list_following_url(self.profile_2.id)
        res = self.client.get(url, {"username": "charlie"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        usernames = [profile["username"] for profile in res.data["results"]]
        self.assertIn("charlie_smith", usernames)
        self.assertIn("charlie_jones", usernames)
        self.assertNotIn("david_williams", usernames)

    def test_list_following_with_username_filter_case_insensitive(self):
        """Test listing following with username filter is case insensitive."""
        user_5 = create_user("test5@example.com", "user5-password-123")
        profile_5 = create_profile("CharlieSmith", user_5,"About charlie.")

        create_follow(self.profile_2, profile_5)

        # Filter with lowercase "charlie" should still match "CharlieSmith"
        url = list_following_url(self.profile_2.id)
        res = self.client.get(url, {"username": "charlie"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["username"], "CharlieSmith")

    def test_list_following_with_username_filter_no_matches(self):
        """Test listing following with username filter that matches nothing returns empty."""
        create_follow(self.profile_2, self.profile_3)

        url = list_following_url(self.profile_2.id)
        res = self.client.get(url, {"username": "nonexistent"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_following_nonexistent_profile_returns_empty(self):
        """Test listing following for nonexistent profile returns empty list."""
        url = list_following_url(99999)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_following_pagination_works(self):
        """Test that following list is paginated correctly."""
        # Create 20 profiles that profile_2 follows (more than page_size of 15)
        for i in range(20):
            user = create_user(f"test{i+10}@example.com", f"password{i+10}")
            profile = create_profile(f"user_{i+10:02d}", user, f"About user {i+10}")
            create_follow(self.profile_2, profile)

        # profile_2 now follows 20 profiles
        url = list_following_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # First page should have 15 results (page_size)
        self.assertEqual(len(res.data["results"]), 15)
        # Check pagination metadata
        self.assertIsNotNone(res.data["next"])
        self.assertIsNone(res.data["previous"])
        self.assertEqual(res.data["count"], 20)

    def test_list_following_pagination_second_page(self):
        """Test that second page of following list returns remaining results."""
        # Create 20 profiles that profile_2 follows
        for i in range(20):
            user = create_user(f"test{i+10}@example.com", f"password{i+10}")
            profile = create_profile(f"user_{i+10:02d}", user, f"About user {i+10}")
            create_follow(self.profile_2, profile)

        # Get second page
        url = list_following_url(self.profile_2.id)
        res = self.client.get(url, {"page": 2})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Second page should have 5 results (20 total - 15 on first page)
        self.assertEqual(len(res.data["results"]), 5)
        self.assertIsNone(res.data["next"])
        self.assertIsNotNone(res.data["previous"])

    def test_list_following_includes_profile_details(self):
        """Test that following list includes full profile details."""
        create_follow(self.profile_2, self.profile_3)

        url = list_following_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res.data["results"]), 0)

        # Check that profile details are included
        following_profile = res.data["results"][0]
        self.assertIn("id", following_profile)
        self.assertIn("username", following_profile)
        self.assertIn("about", following_profile)

    def test_list_following_different_profile_than_authenticated(self):
        """Test listing following for a different profile than authenticated user."""
        # self.profile is authenticated, but check profile_2's following
        create_follow(self.profile_2, self.profile_3)
        create_follow(self.profile_2, self.profile_4)

        url = list_following_url(self.profile_2.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # profile_2 follows profile_3 and profile_4
        self.assertEqual(len(res.data["results"]), 2)

        following_ids = [profile["id"] for profile in res.data["results"]]
        self.assertIn(self.profile_3.id, following_ids)
        self.assertIn(self.profile_4.id, following_ids)

    def test_list_following_own_profile(self):
        """Test listing following for own profile works correctly."""
        # self.profile follows profile_2 (from setUp)
        create_follow(self.profile, self.profile_3)

        url = list_following_url(self.profile.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        following_ids = [profile["id"] for profile in res.data["results"]]
        self.assertIn(self.profile_2.id, following_ids)
        self.assertIn(self.profile_3.id, following_ids)


class PublicListFollowingApiTests(BaseFixtureTestCase):
    """Test the public features of the ListFollowingView API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_list_following_without_authentication_returns_error(self):
        """Test listing following without authentication returns 401."""
        url = list_following_url(self.profile.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


"""
Tests for the Feed api.
"""

from rest_framework import status

from .util import get_feed_url, PostsAppTestHelper


class PrivateFeedApiTests(PostsAppTestHelper):
    """Test the private features of the Feed API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_fetch_feed_successful(self):
        """
        Test fetching a profiles feed returns correct number of posts.
        """
        url = get_feed_url(self.profile.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(len(res.data["results"]), 1)

    def test_fetch_feed_of_another_user_returns_error(self):
        """
        Test fetching a profiles feed that is not a profile of the authenticated user
        returns error. Users should not be able to fetch other users profiles feed.
        """
        url = get_feed_url(self.profile_2.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PublicFeedApiTests(PostsAppTestHelper):
    """Test the public, unauthenticated features of the Feed API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_unauthenticated_fetch_feed_returns_error(self):
        """
        Test fetching a profiles feed while not being authenticated
        returns a 403 error.
        """
        url = get_feed_url(self.profile.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

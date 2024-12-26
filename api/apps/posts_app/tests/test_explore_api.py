"""
Tests for the Explore api.
"""

from rest_framework import status

from .util import PostsAppTestHelper, get_explore_posts_url


class PrivateExploreApiTests(PostsAppTestHelper):
    """Test the private features of the Explore API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_fetch_explore_posts_successful(self):
        """
        Test fetching a profiles explore posts returns posts from profiles that they do not follow.
        """
        url = get_explore_posts_url(self.profile.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(len(res.data["results"]), 4)


class PublicExploreApiTests(PostsAppTestHelper):
    """Test the public, unauthenticated features of the Explore API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_unauthenticated_fetch_explore_posts_returns_error(self):
        """
        Test fetching a profiles explore posts while not being authenticated
        returns a 401 error.
        """
        url = get_explore_posts_url(self.profile.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

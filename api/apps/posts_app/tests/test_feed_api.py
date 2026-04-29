"""
Tests for the Feed api.
"""

from rest_framework import status

from .util import get_feed_url
from core.test_utils.helper_classes import BaseFixtureTestCase


class PrivateFeedApiTests(BaseFixtureTestCase):
    """Test the private features of the Feed API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_fetch_feed_successful(self):
        """
        Test fetching a profiles feed returns correct number of posts.
        """
        url = get_feed_url()

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {post["id"] for post in res.data["results"]}
        self.assertEqual(returned_ids, {self.post_3.id})


class PublicFeedApiTests(BaseFixtureTestCase):
    """Test the public, unauthenticated features of the Feed API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_unauthenticated_fetch_feed_returns_error(self):
        """
        Test fetching a profiles feed while not being authenticated
        returns a 403 error.
        """
        url = get_feed_url()

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

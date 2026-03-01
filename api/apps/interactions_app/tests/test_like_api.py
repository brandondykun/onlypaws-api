"""
Tests for the Likes api.
"""

from rest_framework import status

from .util import create_like_url, destroy_like_url
from core.test_utils.utils import create_like
from core.test_utils.helper_classes import BaseFixtureTestCase

class PrivateLikeApiTests(BaseFixtureTestCase):
    """Test the private features of the Like API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

    def test_like_post_successful(self):
        """
        Test liking a post using valid request returns a 201 response and
        creates the like object in the database.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_3.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count + 1)

    def test_profile_like_own_post_successful(self):
        """
        Test a profile liking own post returns a 201 response and
        creates a like object in the database.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_1.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count + 1)

    def test_unlike_post_successful(self):
        """
        Test un-liking a post using valid request returns a 204 response and
        removes the like object from the database.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        create_like(self.profile, self.post_2)

        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count + 1)

        url = destroy_like_url(self.post_2.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count)

    def test_like_post_from_another_users_auth_profile_returns_error(self):
        """
        Test liking a post using a profile id from a profile that
        does not belong to the authenticated user returns a 400 error.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        new_like = {"profileId": self.profile_2.id}
        url = create_like_url(self.post_2.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # new like should not have been created
        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count)

    def test_unlike_post_where_authenticated_user_has_not_liked_returns_error(self):
        """
        Test un-liking a post where the authenticated user has not liked
        the post returns a 404 error.
        """
        # Create a like from a different profile
        create_like(self.profile_2, self.post_2)

        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 1)

        # Try to unlike as self.profile (who hasn't liked the post)
        url = destroy_like_url(self.post_2.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        
        # Verify the like still exists
        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count)

    def test_unlike_post_where_like_does_not_exist_returns_error(self):
        """
        Test un-liking a post using a valid profile id and post id, but the
        profile has not liked the post returns 404 error.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)  # ensure no likes exist

        # try to unlike a post without the like being created
        url = destroy_like_url(self.post_2.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class PublicLikeApiTests(BaseFixtureTestCase):
    """Test the public features of the Like API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_unauthenticated_like_post_returns_error(self):
        """
        Test liking a post from profile that is not authenticated returns
        401 error and does not create a like object in the database.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_2.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count)

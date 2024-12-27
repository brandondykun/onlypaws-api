"""
Tests for the Likes api.
"""

from rest_framework import status

from .util import PostsAppTestHelper, create_like_url, destroy_like_url, create_like


class PrivateLikeApiTests(PostsAppTestHelper):
    """Test the private features of the Like API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

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

    def test_profile_like_own_post_throws_error(self):
        """
        Test a profile liking own post returns a 403 error and does not
        create a like object in the database.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_1.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        current_likes_count = self.get_likes_count()
        self.assertEqual(current_likes_count, starting_likes_count)

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

        url = destroy_like_url(self.post_2.id, self.profile.id)
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

    def test_unlike_post_from_another_users_auth_profile_returns_error(self):
        """
        Test un-liking a post using a profile id from a profile that
        does not belong to the authenticated user returns a 400 error.
        """
        create_like(self.profile, self.post_2)

        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 1)

        url = destroy_like_url(self.post_2.id, self.profile_3.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unlike_post_where_like_does_not_exist_returns_error(self):
        """
        Test un-liking a post using a valid profile id and post id, but the
        profile has not liked the post returns 404 error.
        """
        starting_likes_count = self.get_likes_count()
        self.assertEqual(starting_likes_count, 0)  # ensure no likes exist

        # try to unlike a post without the like being created
        url = destroy_like_url(self.post_2.id, self.profile.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class PublicLikeApiTests(PostsAppTestHelper):
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

"""
Tests for the Follow api.
"""

from rest_framework import status

from .util import (
    PostsAppTestHelper,
    create_follow,
    create_follow_url,
    create_destroy_follow_url,
)


class PrivateFollowApiTests(PostsAppTestHelper):
    """Test the private features of the Follow API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_follow_profile_successful(self):
        """
        Test following a profile using valid request returns a 201 response and
        creates the follow object in the database.
        """
        starting_follows_count = self.get_follows_count()

        new_follow = {"profileId": self.profile_3.id}
        url = create_follow_url(self.profile.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count + 1)

    def test_follow_profile_already_following_returns_error(self):
        """
        Test following a profile that is already being followed returns a 400 error.
        self.profile is already following profile_2
        """
        starting_follows_count = self.get_follows_count()

        new_follow = {"profileId": self.profile_2.id}
        url = create_follow_url(self.profile.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count)

    def test_follow_self_returns_error(self):
        """
        Test a profile following itself returns error and does not
        create a follow object in the database.
        """
        starting_follows_count = self.get_follows_count()

        new_follow = {"profileId": self.profile.id}
        url = create_follow_url(self.profile.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count)

    def test_follow_from_bad_profile_returns_error(self):
        """
        Test sending a profile that does not belong to the authenticated user returns
        error and does not create a follow object in the database.
        """
        starting_follows_count = self.get_follows_count()

        new_follow = {"profileId": self.profile_2.id}
        url = create_follow_url(self.profile_3.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count)

    def test_destroy_follow_successful(self):
        """
        Test removing a follow is successful and removes
        a follow object from the database.
        """
        starting_follows_count = self.get_follows_count()

        create_follow(self.profile_2, self.profile)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count + 1)

        url = create_destroy_follow_url(self.profile.id, self.profile_2.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count)

    def test_destroy_follow_bad_profile_returns_error(self):
        """
        Test removing a follow for a profile that does not belong to the authenticated user
        returns error and does not delete follow from database.
        """
        starting_follows_count = self.get_follows_count()

        create_follow(self.profile_2, self.profile_3)

        url = create_destroy_follow_url(self.profile_3.id, self.profile_2.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        current_follows_count = self.get_follows_count()
        self.assertEqual(current_follows_count, starting_follows_count + 1)

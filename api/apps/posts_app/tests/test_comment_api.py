"""
Tests for the comment api.
"""

from rest_framework import status

from apps.core_app.models import Comment

from .util import PostsAppTestHelper, create_comment_url, list_post_comments_url


class PrivateCommentApiTests(PostsAppTestHelper):
    """Test the private features of the Comment API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_create_comment_successful(self):
        """Test creating a post comment is successful."""

        new_comment = {
            "profileId": self.profile.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }

        url = create_comment_url(self.post_1.id)
        res = self.client.post(url, new_comment, HTTP_AUTH_PROFILE_ID=self.profile.id)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["profile"]["id"], self.profile.id)
        self.assertEqual(res.data["text"], new_comment["text"])

    def test_listing_post_comments_successful(self):
        """Test listing a posts comments is successful."""

        url = list_post_comments_url(self.post_1.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(res.data["next"], None)
        self.assertEqual(res.data["previous"], None)

        first_comment = res.data["results"][0]
        second_comment = res.data["results"][1]
        # comments are returned reverse sorted by time created (newest first).
        # The last comment created should be returned first in the list
        self.assertEqual(first_comment["text"], self.comment_2.text)
        self.assertEqual(second_comment["text"], self.comment_1.text)

    def test_creating_comment_with_other_users_profile_returns_error(self):
        """
        Test creating a comment using a profile id that does not belong to the authenticated
        user returns error and does not create a comment in the database.
        """
        starting_comment_count = len(Comment.objects.all())

        new_comment = {
            "profileId": self.profile_2.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }

        url = create_comment_url(self.post_1.id)
        res = self.client.post(url, new_comment)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_comments = Comment.objects.all()
        self.assertEqual(len(db_comments), starting_comment_count)

    def test_creating_comment_without_text_returns_error(self):
        """
        Test creating a comment without comment text returns error
        and does not create a comment in the database.
        """
        starting_comment_count = len(Comment.objects.all())

        new_comment = {
            "profileId": self.profile.id,
            "text": "",
            "parent_comment": "",
            "reply_to_comment": "",
        }

        url = create_comment_url(self.post_1.id)
        res = self.client.post(url, new_comment)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_comments = Comment.objects.all()
        self.assertEqual(len(db_comments), starting_comment_count)


class PublicCommentApiTests(PostsAppTestHelper):
    """Test the public features of the Comment API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_create_comment_without_authentication_returns_error(self):
        """
        Test creating a post comment without authentication returns error
        and does not create a comment object in the database.
        """
        starting_comment_count = len(Comment.objects.all())

        new_comment = {
            "profileId": self.profile.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }
        comments = Comment.objects.all()
        self.assertEqual(len(comments), starting_comment_count)

        url = create_comment_url(self.post_1.id)
        res = self.client.post(url, new_comment)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        comments = Comment.objects.all()
        self.assertEqual(len(comments), starting_comment_count)

    def test_listing_post_comments_without_authentication_returns_error(self):
        """
        Test listing a posts comments without authentication returns an error.
        """
        url = list_post_comments_url(self.post_1.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

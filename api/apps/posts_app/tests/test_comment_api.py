"""
Tests for the comment api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, Post, Comment


# id is post id
def create_comment_url(post_id):
    """Create and return a create comment url."""
    return reverse("posts_app:create_comment", args=[post_id])


# post to like pk and profile_id of profile liking the post
def list_post_comments_url(post_id):
    """Create and return a list post comments url."""
    return reverse("posts_app:list_post_comments", args=[post_id])


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


def create_post(**params):
    """Create and return new Post."""
    return Post.objects.create(**params)


def create_comment(**params):
    """Create and return new Comment."""
    return Comment.objects.create(**params)


class PrivateCommentApiTests(TestCase):
    """Test the private features of the Comment API."""

    def setUp(self):
        # create first user
        user_details = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        self.user = create_user(**user_details)
        profile_details = {
            "username": "test_username",
            "about": "Test about text.",
            "user": self.user,
        }
        self.profile = create_profile(**profile_details)
        # create second user
        user_details = {
            "email": "test2@example.com",
            "password": "test-user-password-123",
        }
        self.user_2 = create_user(**user_details)
        profile_details = {
            "username": "test_username2",
            "about": "Test about text 2.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_details)
        # create post for profile 2
        post_data = {
            "caption": "Test Caption 1",
            "profile": self.profile_2,
        }
        self.post = create_post(**post_data)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_comment_successful(self):
        """Test creating a post comment is successful."""
        new_comment = {
            "profileId": self.profile.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }

        url = create_comment_url(self.post.id)
        res = self.client.post(url, new_comment, HTTP_AUTH_PROFILE_ID=self.profile.id)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["profile"]["id"], self.profile.id)
        self.assertEqual(res.data["text"], new_comment["text"])

    def test_listing_post_comments_successful(self):
        """Test listing a posts comments is successful."""
        # create 2 comments
        comment_1 = create_comment(
            profile=self.profile,
            text="Test Comment One",
            post=self.post,
            parent_comment=None,
            reply_to_comment=None,
        )
        comment_2 = create_comment(
            profile=self.profile,
            text="Test Comment Two",
            post=self.post,
            parent_comment=None,
            reply_to_comment=None,
        )

        url = list_post_comments_url(self.post.id)
        res = self.client.get(url, HTTP_AUTH_PROFILE_ID=self.profile.id)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(res.data["next"], None)
        self.assertEqual(res.data["previous"], None)

        first_comment = res.data["results"][0]
        second_comment = res.data["results"][1]
        # comments are returned reverse sorted by time created (newest first).
        # The last comment created should be returned first in the list
        self.assertEqual(first_comment["text"], comment_2.text)
        self.assertEqual(second_comment["text"], comment_1.text)

    def test_creating_comment_with_other_users_profile_returns_error(self):
        """
        Test creating a comment using a profile id that does not belong to the authenticated
        user returns error and does not create a comment in the database.
        """
        new_comment = {
            "profileId": self.profile_2.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }

        url = create_comment_url(self.post.id)
        res = self.client.post(url, new_comment)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_comments = Comment.objects.all()
        self.assertEqual(len(db_comments), 0)


class PublicCommentApiTests(TestCase):
    """Test the public features of the Comment API."""

    def setUp(self):
        # create first user
        user_details = {
            "email": "test@example.com",
            "password": "test-user-password-123",
        }
        self.user = create_user(**user_details)
        profile_details = {
            "username": "test_username",
            "about": "Test about text.",
            "user": self.user,
        }
        self.profile = create_profile(**profile_details)
        # create second user
        user_details = {
            "email": "test2@example.com",
            "password": "test-user-password-123",
        }
        self.user_2 = create_user(**user_details)
        profile_details = {
            "username": "test_username2",
            "about": "Test about text 2.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_details)
        # create post for profile 2
        post_data = {
            "caption": "Test Caption 1",
            "profile": self.profile_2,
        }
        self.post = create_post(**post_data)
        self.client = APIClient()

    def test_create_comment_without_authentication_returns_error(self):
        """
        Test creating a post comment without authentication returns error
        and does not create a comment object in the database.
        """
        new_comment = {
            "profileId": self.profile.id,
            "text": "This is a test comment.",
            "parent_comment": "",
            "reply_to_comment": "",
        }
        comments = Comment.objects.all()
        self.assertEqual(len(comments), 0)

        url = create_comment_url(self.post.id)
        res = self.client.post(url, new_comment)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        comments = Comment.objects.all()
        self.assertEqual(len(comments), 0)

    def test_listing_post_comments_without_authentication_returns_error(self):
        """
        Test listing a posts comments without authentication returns an error.
        """
        # create 2 comments
        create_comment(
            profile=self.profile,
            text="Test Comment One",
            post=self.post,
            parent_comment=None,
            reply_to_comment=None,
        )
        create_comment(
            profile=self.profile,
            text="Test Comment Two",
            post=self.post,
            parent_comment=None,
            reply_to_comment=None,
        )

        url = list_post_comments_url(self.post.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

"""
Tests for the Feed api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, Post, Like, Follow

CREATE_POST_URL = reverse("posts_app:create_post")


# post id to like
def create_like_url(post_id):
    """Create and return a create like post url."""
    return reverse("posts_app:create_like", args=[post_id])


# post to like pk and profile_id of profile liking the post
def destroy_like_url(pk, profile_id):
    """Create and return a destroy like url."""
    return reverse("posts_app:destroy_like", args=[pk, profile_id])


def get_feed_url(profile_id):
    """Create and return a get feed url."""
    return reverse("posts_app:retrieve_feed", args=[profile_id])


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


def create_post(**params):
    """Create and return new Post."""
    return Post.objects.create(**params)


def create_like(**params):
    """Create and return new Like."""
    return Like.objects.create(**params)


def create_follow(**params):
    """Create and return new Follow."""
    return Follow.objects.create(**params)


class PrivateFeedApiTests(TestCase):
    """Test the private features of the Feed API."""

    def setUp(self):
        # Create a user and profile
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
        # create post for profile 1
        post_1_data = {
            "caption": "Test Caption 1",
            "profile": self.profile,
        }
        self.post_1 = create_post(**post_1_data)
        # Create a second user and profile
        user_2_details = {
            "email": "test2@example.com",
            "password": "test-user2-password-123",
        }
        self.user_2 = create_user(**user_2_details)
        profile_2_details = {
            "username": "test2_username",
            "about": "Test about text 2.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_2_details)
        # create post for profile 2
        post_2_data = {
            "caption": "Test Caption 2",
            "profile": self.profile_2,
        }
        self.post_2 = create_post(**post_2_data)
        post_3_data = {
            "caption": "Test Caption 3",
            "profile": self.profile_2,
        }
        self.post_3 = create_post(**post_3_data)
        post_4_data = {
            "caption": "Test Caption 4",
            "profile": self.profile_2,
        }
        self.post_4 = create_post(**post_4_data)

        self.follow = create_follow(followed_by=self.profile, followed=self.profile_2)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_fetch_feed_successful(self):
        """
        Test fetching a profiles feed returns correct number of posts.
        """
        url = get_feed_url(self.profile.id)

        res = self.client.get(url, HTTP_AUTH_PROFILE_ID=self.profile.id)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(len(res.data["results"]), 3)

    def test_fetch_feed_of_another_user_returns_error(self):
        """
        Test fetching a profiles feed that is not a profile of the authenticated user
        returns error. Users should not be able to fetch other users profiles feed.
        """
        url = get_feed_url(self.profile_2.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PublicFeedApiTests(TestCase):
    """Test the public, unauthenticated features of the Feed API."""

    def setUp(self):
        # Create a user and profile
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
        # create post for profile 1
        post_1_data = {
            "caption": "Test Caption 1",
            "profile": self.profile,
        }
        self.post_1 = create_post(**post_1_data)
        # Create a second user and profile
        user_2_details = {
            "email": "test2@example.com",
            "password": "test-user2-password-123",
        }
        self.user_2 = create_user(**user_2_details)
        profile_2_details = {
            "username": "test2_username",
            "about": "Test about text 2.",
            "user": self.user_2,
        }
        self.profile_2 = create_profile(**profile_2_details)
        # create post for profile 2
        post_2_data = {
            "caption": "Test Caption 2",
            "profile": self.profile_2,
        }
        self.post_2 = create_post(**post_2_data)
        post_3_data = {
            "caption": "Test Caption 3",
            "profile": self.profile_2,
        }
        self.post_3 = create_post(**post_3_data)
        post_4_data = {
            "caption": "Test Caption 4",
            "profile": self.profile_2,
        }
        self.post_4 = create_post(**post_4_data)

        self.follow = create_follow(followed_by=self.profile, followed=self.profile_2)

        self.client = APIClient()
        # self.client.force_authenticate(user=self.user)

    def test_unauthenticated_fetch_feed_returns_error(self):
        """
        Test fetching a profiles feed while not being authenticated
        returns a 403 error.
        """
        url = get_feed_url(self.profile.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

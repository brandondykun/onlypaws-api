"""
Tests for the Likes api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, Post, Like

CREATE_POST_URL = reverse("posts_app:create_post")
CREATE_DESTROY_LIKE_URL = reverse("posts_app:create_destroy_like")


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


def create_post(**params):
    """Create and return new Post."""
    return Post.objects.create(**params)


class PrivateLikeApiTests(TestCase):
    """Test the private features of the Posts API."""

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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_like_post_successful(self):
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"post": self.post_2.id}
        res = self.client.post(CREATE_DESTROY_LIKE_URL, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 1)

    def test_profile_like_own_post_throws_error(self):
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"post": self.post_1.id}
        res = self.client.post(CREATE_DESTROY_LIKE_URL, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 0)

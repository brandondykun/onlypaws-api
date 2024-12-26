"""
Tests for the posts api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from apps.core_app.models import Profile, Post

CREATE_POST_URL = reverse("posts_app:create_post")


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


class PrivatePostsApiTests(APITestCase):
    """Test the private features of the Posts API."""

    def setUp(self):
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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_create_post_without_caption_returns_error(self):
        """
        Test creating a Post without a caption returns 400 error and
        does not create a Post object in the database.
        """
        new_post = {
            "caption": "",
            "profileId": self.profile.id,
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        all_posts = Post.objects.all()
        self.assertEqual(len(all_posts), 0)

    def test_create_post_success(self):
        """Test successfully creating a Post"""

        new_post = {
            "caption": "Test caption",
            "profileId": self.profile.id,
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.data["caption"], new_post["caption"])
        expected_profile = {
            "id": self.profile.id,
            "username": self.profile.username,
            "about": self.profile.about,
            "name": self.profile.name,
            "image": None,
            "breed": None,
            "pet_type": None,
        }
        self.assertEqual(res.data["profile"], expected_profile)

        all_posts = Post.objects.all()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(all_posts), 1)

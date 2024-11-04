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


# post id to like
def create_like_url(post_id):
    """Create and return a create like post url."""
    return reverse("posts_app:create_like", args=[post_id])


# post to like pk and profile_id of profile liking the post
def destroy_like_url(pk, profile_id):
    """Create and return a destroy like url."""
    return reverse("posts_app:destroy_like", args=[pk, profile_id])


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


class PrivateLikeApiTests(TestCase):
    """Test the private features of the Posts API."""

    def setUp(self):
        # Create 3 users and profiles
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
        # Create third user and profile
        user_3_details = {
            "email": "test3@example.com",
            "password": "test-user-password-123",
        }
        self.user_3 = create_user(**user_3_details)
        profile_3_details = {
            "username": "test_username3",
            "about": "Test about text 3.",
            "user": self.user_3,
        }
        self.profile_3 = create_profile(**profile_3_details)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_like_post_successful(self):
        """
        Test liking a post using valid request returns a 201 response and
        creates the like object in the database.
        """
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_2.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 1)

    def test_profile_like_own_post_throws_error(self):
        """
        Test a profile liking own post returns a 403 error and does not
        create a like object in the database.
        """
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_1.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 0)

    def test_unlike_post_successful(self):
        """
        Test un-liking a post using valid request returns a 204 response and
        removes the like object from the database.
        """
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        create_like(profile=self.profile, post=self.post_2)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 1)

        url = destroy_like_url(self.post_2.id, self.profile.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 0)

    def test_like_post_from_another_users_auth_profile_returns_error(self):
        """
        Test liking a post using a profile id from a profile that
        does not belong to the authenticated user returns a 400 error.
        """
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"profileId": self.profile_2.id}
        url = create_like_url(self.post_2.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # new like should not have been created
        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 0)

    def test_unlike_post_from_another_users_auth_profile_returns_error(self):
        """
        Test un-liking a post using a profile id from a profile that
        does not belong to the authenticated user returns a 400 error.
        """
        create_like(profile=self.profile, post=self.post_2)

        likes = Like.objects.all()
        self.assertEqual(len(likes), 1)

        url = destroy_like_url(self.post_2.id, self.profile_3.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unlike_post_where_like_does_not_exist_returns_error(self):
        """
        Test un-liking a post using a valid profile id and post id, but the
        profile has not liked the post returns 404 error.
        """
        likes = Like.objects.all()
        self.assertEqual(len(likes), 0)  # ensure no likes exist

        # try to unlike a post without the like being created
        url = destroy_like_url(self.post_2.id, self.profile.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class PublicLikeApiTests(TestCase):
    """Test the public features of the Posts API."""

    def setUp(self):
        # Create 3 users and profiles
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
        # Create third user and profile
        user_3_details = {
            "email": "test3@example.com",
            "password": "test-user-password-123",
        }
        self.user_3 = create_user(**user_3_details)
        profile_3_details = {
            "username": "test_username3",
            "about": "Test about text 3.",
            "user": self.user_3,
        }
        self.profile_3 = create_profile(**profile_3_details)
        self.client = APIClient()

    def test_unauthenticated_like_post_returns_error(self):
        """
        Test liking a post from profile that is not authenticated returns
        401 error and does not create a like object in the database.
        """
        all_likes = Like.objects.all()
        self.assertEqual(len(all_likes), 0)

        new_like = {"profileId": self.profile.id}
        url = create_like_url(self.post_2.id)
        res = self.client.post(url, data=new_like)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        updated_likes = Like.objects.all()
        self.assertEqual(len(updated_likes), 0)

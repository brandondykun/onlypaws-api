"""
Tests for the Follow api.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.core_app.models import Profile, Post, Follow


# profile id of authenticated user profile
def create_follow_url(auth_profile_id):
    """Create and return a create follow url."""
    return reverse("posts_app:create_follow", args=[auth_profile_id])


# profile id of authenticated user profile and profile id of profile being followed
def create_destroy_follow_url(auth_profile_id, followed_profile_id):
    """Create and return a destroy follow url."""
    return reverse(
        "posts_app:destroy_follow", args=[auth_profile_id, followed_profile_id]
    )


def create_user(**params):
    """Create and return new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return new Profile."""
    return Profile.objects.create(**params)


def create_post(**params):
    """Create and return new Post."""
    return Post.objects.create(**params)


def create_follow(**params):
    """Create and return new Follow."""
    return Follow.objects.create(**params)


class PrivateFollowApiTests(TestCase):
    """Test the private features of the Follow API."""

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

    def test_follow_profile_successful(self):
        """
        Test following a profile using valid request returns a 201 response and
        creates the follow object in the database.
        """
        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

        new_follow = {"profileId": self.profile_2.id}
        url = create_follow_url(self.profile.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 1)

    def test_follow_self_returns_error(self):
        """
        Test a profile following itself returns error and does not
        create a follow object in the database.
        """
        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

        new_follow = {"profileId": self.profile.id}
        url = create_follow_url(self.profile.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

    def test_follow_from_bad_profile_returns_error(self):
        """
        Test sending a profile that does not belong to the authenticated user returns
        error and does not create a follow object in the database.
        """
        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

        new_follow = {"profileId": self.profile_2.id}
        url = create_follow_url(self.profile_3.id)

        res = self.client.post(url, data=new_follow)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

    def test_destroy_follow_successful(self):
        """
        Test removing a follow is successful and removes
        a follow object from the database.
        """

        create_follow(followed=self.profile_2, followed_by=self.profile)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 1)

        url = create_destroy_follow_url(self.profile.id, self.profile_2.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 0)

    def test_destroy_follow_bad_profile_returns_error(self):
        """
        Test removing a follow for a profile that does not belong to the authenticated user
        returns error and does not delete follow from database.
        """

        create_follow(followed=self.profile_2, followed_by=self.profile_3)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 1)

        url = create_destroy_follow_url(self.profile_3.id, self.profile_2.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        db_follows = Follow.objects.all()
        self.assertEqual(len(db_follows), 1)

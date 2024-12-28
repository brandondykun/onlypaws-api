"""
Tests for the Posts api.
"""

from rest_framework import status
from apps.core_app.models import Post

from .util import (
    CREATE_POST_URL,
    PostsAppTestHelper,
    retrieve_destroy_post_url,
    create_post,
)


class PrivatePostsApiTests(PostsAppTestHelper):
    """Test the private features of the Posts API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_create_post_without_caption_returns_error(self):
        """
        Test creating a Post without a caption returns 400 error and
        does not create a Post object in the database.
        """
        starting_post_count = self.get_posts_count()

        new_post = {
            "caption": "",
            "profileId": self.profile.id,
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count)

    def test_create_post_success(self):
        """
        Test successfully creating a Post returns 201 and
        creates Post object in database.
        """
        starting_post_count = self.get_posts_count()

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
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_fetching_single_post_success(self):
        """
        Test successfully fetching a single Post successfully returns Post details.
        """
        sample_post = Post.objects.first()

        url = retrieve_destroy_post_url(sample_post.id)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        is_liked = sample_post.likes.filter(profile=self.profile.id).exists()
        is_saved = sample_post.saved_by.filter(profile=self.profile.id).exists()

        self.assertEqual(sample_post.id, res.data["id"])
        self.assertEqual(sample_post.caption, res.data["caption"])
        self.assertEqual(sample_post.profile.id, res.data["profile"]["id"])
        self.assertEqual(sample_post.comments.count(), res.data["comments_count"])
        self.assertEqual(sample_post.likes.count(), res.data["likes_count"])
        self.assertEqual(is_liked, res.data["liked"])
        self.assertEqual(is_saved, res.data["is_saved"])

    def test_deleting_post_success(self):
        """
        Test deleting a Post is successful.
        """
        starting_post_count = self.get_posts_count()

        new_post = create_post("Delete me caption", self.profile)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

        url = retrieve_destroy_post_url(new_post.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count)
        self.assertEqual(len(Post.objects.filter(id=new_post.id)), 0)

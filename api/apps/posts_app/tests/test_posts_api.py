"""
Tests for the Posts api.
"""

from rest_framework import status
from django.core.exceptions import ValidationError
from apps.posts_app.models import Post, PostImage

from .util import (
    CREATE_POST_URL,
    PostsAppTestHelper,
    retrieve_destroy_post_url,
    destroy_post_image_url,
    create_post,
    create_post_image,
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
            "breed": "",
            "pet_type": None,
            "profile_type": "regular",
        }
        self.assertEqual(res.data["profile"], expected_profile)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_1000_character_caption_success(self):
        """
        Test creating a Post with exactly 1000 characters succeeds.
        """
        starting_post_count = self.get_posts_count()
        
        # Create a caption with exactly 1000 characters
        caption_1000_chars = "a" * 1000
        
        new_post = {
            "caption": caption_1000_chars,
            "profileId": self.profile.id,
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["caption"], caption_1000_chars)

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_1001_character_caption_fails(self):
        """
        Test creating a Post with 1001 characters fails with validation error.
        """
        starting_post_count = self.get_posts_count()
        
        # Create a caption with 1001 characters (exceeds limit)
        caption_1001_chars = "a" * 1001
        
        new_post = {
            "caption": caption_1001_chars,
            "profileId": self.profile.id,
            "images": [],
            "order": []
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", res.data)
        self.assertIn("Error creating that post.", str(res.data["message"]))

        # Ensure no post was created
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count)

    def test_update_post_with_1000_character_caption_success(self):
        """
        Test updating a Post caption with exactly 1000 characters succeeds.
        """
        # Create a post first
        post = create_post("Original caption", self.profile)
        
        # Create a caption with exactly 1000 characters
        caption_1000_chars = "b" * 1000
        
        url = retrieve_destroy_post_url(post.id)
        update_data = {"caption": caption_1000_chars}

        res = self.client.patch(url, data=update_data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["caption"], caption_1000_chars)

        # Verify in database
        post.refresh_from_db()
        self.assertEqual(post.caption, caption_1000_chars)

    def test_update_post_with_1001_character_caption_fails(self):
        """
        Test updating a Post caption with 1001 characters fails with validation error.
        """
        # Create a post first
        original_caption = "Original caption"
        post = create_post(original_caption, self.profile)
        
        # Create a caption with 1001 characters (exceeds limit)
        caption_1001_chars = "b" * 1001
        
        url = retrieve_destroy_post_url(post.id)
        update_data = {"caption": caption_1001_chars}

        res = self.client.patch(url, data=update_data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("caption", res.data)
        self.assertIn("cannot exceed 1000 characters", str(res.data["caption"][0]))

        # Verify caption wasn't changed in database
        post.refresh_from_db()
        self.assertEqual(post.caption, original_caption)

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

    def test_delete_post_image_success(self):
        """
        Test deleting a PostImage is successful when post has multiple images.
        """
        # Create a post with multiple images
        post = create_post("Test post with images", self.profile)
        image1 = create_post_image(post)
        image2 = create_post_image(post)
        
        # Verify we have 2 images
        self.assertEqual(post.images.count(), 2)
        
        # Delete one image
        url = destroy_post_image_url(image1.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify the image was deleted and post still exists
        self.assertEqual(post.images.count(), 1)
        self.assertEqual(PostImage.objects.filter(id=image1.id).count(), 0)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_delete_last_post_image_fails(self):
        """
        Test deleting the last PostImage of a post fails with appropriate error.
        """
        # Create a post with only one image
        post = create_post("Test post with one image", self.profile)
        image = create_post_image(post)
        
        # Verify we have 1 image
        self.assertEqual(post.images.count(), 1)
        
        # Try to delete the only image
        url = destroy_post_image_url(image.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot delete the last image", res.data["error"])
        
        # Verify the image was not deleted
        self.assertEqual(post.images.count(), 1)
        self.assertTrue(PostImage.objects.filter(id=image.id).exists())

    def test_delete_post_image_unauthorized_user_fails(self):
        """
        Test deleting a PostImage by unauthorized user fails.
        """
        # Create a post with image owned by profile_2
        post = create_post("Test post", self.profile_2)
        image = create_post_image(post)
        
        # Try to delete the image as self.profile (different user)
        url = destroy_post_image_url(image.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("does not own this resource", res.data["error"])
        
        # Verify the image was not deleted
        self.assertTrue(PostImage.objects.filter(id=image.id).exists())

    def test_delete_nonexistent_post_image_fails(self):
        """
        Test deleting a non-existent PostImage returns 404.
        """
        url = destroy_post_image_url(99999)  # Non-existent ID
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_model_caption_validation_1000_chars_success(self):
        """
        Test that Post model accepts exactly 1000 characters in caption.
        """
        caption_1000_chars = "c" * 1000
        
        # Create post with 1000 character caption
        post = Post(
            caption=caption_1000_chars,
            profile=self.profile,
            contains_ai=False
        )
        
        # This should not raise a ValidationError
        try:
            post.full_clean()  # This runs model validation including validators
            post.save()
            self.assertEqual(post.caption, caption_1000_chars)
        except ValidationError:
            self.fail("ValidationError raised for 1000 character caption")

    def test_post_model_caption_validation_1001_chars_fails(self):
        """
        Test that Post model rejects 1001 characters in caption.
        """
        caption_1001_chars = "c" * 1001
        
        # Create post with 1001 character caption
        post = Post(
            caption=caption_1001_chars,
            profile=self.profile,
            contains_ai=False
        )
        
        # This should raise a ValidationError
        with self.assertRaises(ValidationError) as context:
            post.full_clean()  # This runs model validation including validators
        
        # Verify the error is about caption length
        self.assertIn('caption', context.exception.message_dict)
        self.assertIn('1000', str(context.exception.message_dict['caption'][0]))

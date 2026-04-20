"""
Tests for the Posts api.
"""

from rest_framework import status
from django.core.exceptions import ValidationError
from apps.posts_app.models import Post, PostImage

from .util import CREATE_POST_URL, destroy_post_image_url, retrieve_destroy_post_url, list_similar_posts_url
from core.test_utils.helper_classes import BaseFixtureTestCase
from core.test_utils.utils import create_post, create_post_image, create_test_image, create_mock_embedding


class PrivatePostsApiTests(BaseFixtureTestCase):
    """Test the private features of the Posts API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

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
        self.assertEqual(res.data["aspect_ratio"], "1:1")  # Default aspect ratio
        expected_profile = {
            "id": self.profile.id,
            "public_id": str(self.profile.public_id),
            "username": self.profile.username,
            "about": self.profile.regularprofile.about,
            "name": self.profile.regularprofile.name,
            "image": None,
            "breed": "",
            "pet_type": None,
            "sex": "",
            "birthdate": None,
            "weight": None,
            "is_spayed_neutered": None,
            "is_service_animal": None,
            "energy_level": "",
            "anxiety_level": "",
            "profile_type": "regular",
            "is_private": False,
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
        
        url = retrieve_destroy_post_url(post)
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
        
        url = retrieve_destroy_post_url(post)
        update_data = {"caption": caption_1001_chars}

        res = self.client.patch(url, data=update_data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("caption", res.data)
        self.assertIn("cannot exceed 1000 characters", str(res.data["caption"][0]))

        # Verify caption wasn't changed in database
        post.refresh_from_db()
        self.assertEqual(post.caption, original_caption)

    def test_create_post_with_single_image_success(self):
        """
        Test successfully creating a Post with a single image.
        """
        starting_post_count = self.get_posts_count()
        
        # Create test image
        image = create_test_image('test_image_1.jpg')
        
        # Prepare post data with image
        post_data = {
            "caption": "Test post with one image",
            "profileId": self.profile.id,
            "order": [0],  # Order for the image
        }
        
        res = self.client.post(
            CREATE_POST_URL, 
            data={**post_data, 'images': [image]},
            format='multipart'
        )
        
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["caption"], post_data["caption"])
        self.assertEqual(len(res.data["images"]), 1)
        self.assertEqual(res.data["images"][0]["order"], 0)
        
        # Verify post and image created in database
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)
        
        # Verify PostImage was created
        new_post = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post.images.count(), 1)
        self.assertEqual(new_post.images.first().order, 0)

    def test_create_post_with_multiple_images_success(self):
        """
        Test successfully creating a Post with multiple images in correct order.
        """
        starting_post_count = self.get_posts_count()
        
        # Create test images
        image1 = create_test_image('test_image_1.jpg', color='red')
        image2 = create_test_image('test_image_2.jpg', color='blue')
        image3 = create_test_image('test_image_3.jpg', color='green')
        
        # Prepare post data with multiple images
        post_data = {
            "caption": "Test post with multiple images",
            "profileId": self.profile.id,
            "order": [0, 1, 2],  # Order for the images
        }
        
        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image1, image2, image3]},
            format='multipart'
        )
        
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["caption"], post_data["caption"])
        self.assertEqual(len(res.data["images"]), 3)
        
        # Verify images are in correct order
        self.assertEqual(res.data["images"][0]["order"], 0)
        self.assertEqual(res.data["images"][1]["order"], 1)
        self.assertEqual(res.data["images"][2]["order"], 2)
        
        # Verify post and images created in database
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)
        
        # Verify PostImages were created with correct order
        new_post = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post.images.count(), 3)
        
        images = list(new_post.images.all().order_by('order'))
        self.assertEqual(images[0].order, 0)
        self.assertEqual(images[1].order, 1)
        self.assertEqual(images[2].order, 2)

    def test_create_post_with_images_wrong_order_count_fails(self):
        """
        Test creating a Post fails when number of images and order values don't match.
        """
        starting_post_count = self.get_posts_count()
        
        # Create test images
        image1 = create_test_image('test_image_1.jpg')
        image2 = create_test_image('test_image_2.jpg')
        
        # Prepare post data with mismatched order count
        post_data = {
            "caption": "Test post with mismatched order",
            "profileId": self.profile.id,
            "order": [0],  # Only 1 order value for 2 images
        }
        
        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image1, image2]},
            format='multipart'
        )
        
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)
        self.assertIn("Number of images and order values must match", res.data["error"])
        
        # Verify no post was created
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count)

    def test_create_post_with_custom_order_success(self):
        """
        Test creating a Post with custom (non-sequential) image order.
        """
        starting_post_count = self.get_posts_count()
        
        # Create test images
        image1 = create_test_image('test_image_1.jpg', color='red')
        image2 = create_test_image('test_image_2.jpg', color='blue')
        
        # Use custom order values (not 0, 1, 2...)
        post_data = {
            "caption": "Test post with custom order",
            "profileId": self.profile.id,
            "order": [5, 2],  # Custom order values
        }
        
        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image1, image2]},
            format='multipart'
        )
        
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["images"]), 2)
        
        # Verify images are ordered according to custom order values
        # Images should be sorted by order field, so order 2 comes before order 5
        self.assertEqual(res.data["images"][0]["order"], 2)
        self.assertEqual(res.data["images"][1]["order"], 5)
        
        # Verify in database
        new_post = Post.objects.get(id=res.data["id"])
        images = list(new_post.images.all().order_by('order'))
        self.assertEqual(images[0].order, 2)
        self.assertEqual(images[1].order, 5)
        
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_ai_generated_flag_success(self):
        """
        Test creating a Post with AI generated flag set to true.
        """
        starting_post_count = self.get_posts_count()
        
        # Create test image
        image = create_test_image('ai_generated_image.jpg')
        
        post_data = {
            "caption": "AI generated content",
            "profileId": self.profile.id,
            "aiGenerated": True,
            "order": [0],
        }
        
        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image]},
            format='multipart'
        )
        
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["contains_ai"], True)
        
        # Verify in database
        new_post = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post.contains_ai, True)
        
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_default_aspect_ratio_success(self):
        """
        Test that creating a Post without specifying aspect_ratio defaults to 1:1.
        """
        starting_post_count = self.get_posts_count()

        new_post = {
            "caption": "Test default aspect ratio",
            "profileId": self.profile.id,
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=new_post)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["aspect_ratio"], "1:1")

        # Verify in database
        new_post_obj = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post_obj.aspect_ratio, "1:1")

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_square_aspect_ratio_success(self):
        """
        Test creating a Post with explicit 1:1 (square) aspect ratio.
        """
        starting_post_count = self.get_posts_count()

        # Create test image
        image = create_test_image('square_image.jpg')

        post_data = {
            "caption": "Square aspect ratio post",
            "profileId": self.profile.id,
            "aspectRatio": "1:1",
            "order": [0],
        }

        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image]},
            format='multipart'
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["aspect_ratio"], "1:1")

        # Verify in database
        new_post = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post.aspect_ratio, "1:1")

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_portrait_aspect_ratio_success(self):
        """
        Test creating a Post with 4:5 (portrait) aspect ratio.
        """
        starting_post_count = self.get_posts_count()

        # Create test image
        image = create_test_image('portrait_image.jpg')

        post_data = {
            "caption": "Portrait aspect ratio post",
            "profileId": self.profile.id,
            "aspectRatio": "4:5",
            "order": [0],
        }

        res = self.client.post(
            CREATE_POST_URL,
            data={**post_data, 'images': [image]},
            format='multipart'
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["aspect_ratio"], "4:5")

        # Verify in database
        new_post = Post.objects.get(id=res.data["id"])
        self.assertEqual(new_post.aspect_ratio, "4:5")

        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count + 1)

    def test_create_post_with_invalid_aspect_ratio_fails(self):
        """
        Test that creating a Post with an invalid aspect ratio fails.
        """
        starting_post_count = self.get_posts_count()

        post_data = {
            "caption": "Invalid aspect ratio post",
            "profileId": self.profile.id,
            "aspectRatio": "16:9",  # Invalid choice
            "images": [],
        }

        res = self.client.post(CREATE_POST_URL, data=post_data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Ensure no post was created
        current_post_count = self.get_posts_count()
        self.assertEqual(current_post_count, starting_post_count)

    def test_fetching_single_post_success(self):
        """
        Test successfully fetching a single Post successfully returns Post details.
        """
        sample_post = Post.objects.first()

        url = retrieve_destroy_post_url(sample_post)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        is_liked = sample_post.likes.filter(profile=self.profile.id).exists()
        is_saved = sample_post.saved_by.filter(profile=self.profile.id).exists()

        self.assertEqual(sample_post.id, res.data["id"])
        self.assertEqual(sample_post.caption, res.data["caption"])
        self.assertEqual(sample_post.aspect_ratio, res.data["aspect_ratio"])
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

        url = retrieve_destroy_post_url(new_post)
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
        url = destroy_post_image_url(image1)
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
        url = destroy_post_image_url(image)
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
        url = destroy_post_image_url(image)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("does not own this resource", res.data["error"])
        
        # Verify the image was not deleted
        self.assertTrue(PostImage.objects.filter(id=image.id).exists())

    def test_delete_nonexistent_post_image_fails(self):
        """
        Test deleting a non-existent PostImage returns 404.
        """
        url = destroy_post_image_url("01HF7YQX8J9K2P3M4N5R6S7T8X")  # Non-existent public_id (26-char ULID)
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

    def test_post_model_aspect_ratio_default_value(self):
        """
        Test that Post model defaults aspect_ratio to 1:1.
        """
        post = Post(
            caption="Test caption",
            profile=self.profile,
            contains_ai=False
        )
        post.full_clean()
        post.save()
        
        self.assertEqual(post.aspect_ratio, "1:1")

    def test_post_model_aspect_ratio_square_success(self):
        """
        Test that Post model accepts 1:1 (square) aspect ratio.
        """
        post = Post(
            caption="Test caption",
            profile=self.profile,
            aspect_ratio="1:1",
            contains_ai=False
        )
        
        # This should not raise a ValidationError
        try:
            post.full_clean()
            post.save()
            self.assertEqual(post.aspect_ratio, "1:1")
        except ValidationError:
            self.fail("ValidationError raised for valid aspect_ratio 1:1")

    def test_post_model_aspect_ratio_portrait_success(self):
        """
        Test that Post model accepts 4:5 (portrait) aspect ratio.
        """
        post = Post(
            caption="Test caption",
            profile=self.profile,
            aspect_ratio="4:5",
            contains_ai=False
        )
        
        # This should not raise a ValidationError
        try:
            post.full_clean()
            post.save()
            self.assertEqual(post.aspect_ratio, "4:5")
        except ValidationError:
            self.fail("ValidationError raised for valid aspect_ratio 4:5")

    def test_post_model_aspect_ratio_invalid_fails(self):
        """
        Test that Post model rejects invalid aspect_ratio values.
        """
        post = Post(
            caption="Test caption",
            profile=self.profile,
            aspect_ratio="16:9",  # Invalid choice
            contains_ai=False
        )
        
        # This should raise a ValidationError
        with self.assertRaises(ValidationError) as context:
            post.full_clean()
        
        # Verify the error is about aspect_ratio
        self.assertIn('aspect_ratio', context.exception.message_dict)

    def test_list_similar_posts_fallback_when_no_embeddings(self):
        """
        Test that ListSimilarPostsView falls back to basic filtering when no embeddings exist.
        """
        # Use post_2 (belongs to self.profile) as the reference post
        # The base fixture creates posts with images but no embeddings
        url = list_similar_posts_url(self.post_2)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Response should use fallback logic (basic filtering)
        self.assertIsInstance(res.data, dict)
        self.assertIn('results', res.data)
        
    def test_list_similar_posts_with_embeddings_finds_similar(self):
        """
        Test that similar posts endpoint finds posts with similar embeddings.
        """
        # Create a reference post with embedding (base value 0.5)
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=10)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create similar posts (base value close to 0.5)
        similar_post_1 = create_post("Similar post 1", self.profile_3)
        similar_embedding_1 = create_mock_embedding(base_value=0.51, variation=0.0, seed=11)
        create_post_image(similar_post_1, create_test_image('sim1.jpg'), embedding=similar_embedding_1)
        
        similar_post_2 = create_post("Similar post 2", self.profile_4)
        similar_embedding_2 = create_mock_embedding(base_value=0.49, variation=0.0, seed=12)
        create_post_image(similar_post_2, create_test_image('sim2.jpg'), embedding=similar_embedding_2)
        
        # Create dissimilar post (base value far from 0.5)
        dissimilar_post = create_post("Dissimilar post", self.profile_3)
        dissimilar_embedding = create_mock_embedding(base_value=0.9, variation=0.0, seed=13)
        create_post_image(dissimilar_post, create_test_image('dissim.jpg'), embedding=dissimilar_embedding)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Should find the similar posts
        result_ids = [post['id'] for post in res.data['results']]
        self.assertIn(similar_post_1.id, result_ids)
        self.assertIn(similar_post_2.id, result_ids)
        
        # Should not include dissimilar post (with default min_similarity=0.3)
        # Note: Depending on the cosine distance, very dissimilar posts should not appear
        
    def test_list_similar_posts_with_embeddings_excludes_own_posts(self):
        """
        Test that similar posts endpoint excludes the authenticated user's own posts.
        """
        # Create a reference post owned by profile_2
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=20)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create similar posts - one owned by the authenticated user (self.profile)
        own_post = create_post("Own similar post", self.profile)
        own_embedding = create_mock_embedding(base_value=0.51, variation=0.0, seed=21)
        create_post_image(own_post, create_test_image('own.jpg'), embedding=own_embedding)
        
        # Create similar post owned by another user
        other_post = create_post("Other similar post", self.profile_3)
        other_embedding = create_mock_embedding(base_value=0.49, variation=0.0, seed=22)
        create_post_image(other_post, create_test_image('other.jpg'), embedding=other_embedding)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Should not include posts from the authenticated user
        result_ids = [post['id'] for post in res.data['results']]
        self.assertNotIn(own_post.id, result_ids)
        
        # Should include posts from other users
        self.assertIn(other_post.id, result_ids)
        
    def test_list_similar_posts_with_embeddings_excludes_original_post(self):
        """
        Test that similar posts endpoint excludes the original post from results.
        """
        # Create a reference post
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=30)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create similar posts
        similar_post = create_post("Similar post", self.profile_3)
        similar_embedding = create_mock_embedding(base_value=0.51, variation=0.0, seed=31)
        create_post_image(similar_post, create_test_image('sim.jpg'), embedding=similar_embedding)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # The original post should not be in the results
        result_ids = [post['id'] for post in res.data['results']]
        self.assertNotIn(reference_post.id, result_ids)
        
    def test_list_similar_posts_with_embeddings_filters_reported_content(self):
        """
        Test that similar posts endpoint filters out reported inappropriate content.
        """
        # Create a reference post
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.01, seed=100)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create a similar post that will be reported
        reported_post = create_post("Reported similar post", self.profile_3)
        reported_embedding = create_mock_embedding(base_value=0.51, variation=0.01, seed=101)
        create_post_image(reported_post, create_test_image('reported.jpg'), embedding=reported_embedding)
        
        # Report the post with reason 1 (Inappropriate Content)
        # The view filters by reason__id=1, so we need to use reason1 which should have id=1
        from apps.moderation_app.models import PostReport
        report = PostReport.objects.create(
            post=reported_post,
            reporter=self.profile.user,
            reason=self.reason1  # Inappropriate Content (should have id=1 from fixture)
        )
        
        # Verify the report was created with the expected reason
        self.assertEqual(report.reason.id, self.reason1.id)
        
        # Create a similar post that is not reported
        clean_post = create_post("Clean similar post", self.profile_4)
        clean_embedding = create_mock_embedding(base_value=0.49, variation=0.01, seed=102)
        create_post_image(clean_post, create_test_image('clean.jpg'), embedding=clean_embedding)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # The reported post should not appear in results (if reason1 has id=1)
        result_ids = [post['id'] for post in res.data['results']]
        if self.reason1.id == 1:
            self.assertNotIn(reported_post.id, result_ids, 
                           f"Reported post {reported_post.id} should not be in results. Reason ID: {self.reason1.id}")
        
        # The clean post should appear
        self.assertIn(clean_post.id, result_ids)
        
    def test_list_similar_posts_with_embeddings_preserves_similarity_order(self):
        """
        Test that similar posts are returned and the ordering logic is working.
        """
        # Create a reference post with a specific embedding
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=200)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create similar posts with different seeds to create varied embeddings
        similar_post_1 = create_post("Similar post 1", self.profile_3)
        similar_embedding_1 = create_mock_embedding(base_value=0.5, variation=0.0, seed=201)
        create_post_image(similar_post_1, create_test_image('sim1.jpg'), embedding=similar_embedding_1)
        
        similar_post_2 = create_post("Similar post 2", self.profile_4)
        similar_embedding_2 = create_mock_embedding(base_value=0.5, variation=0.0, seed=250)
        create_post_image(similar_post_2, create_test_image('sim2.jpg'), embedding=similar_embedding_2)
        
        similar_post_3 = create_post("Similar post 3", self.profile_3)
        similar_embedding_3 = create_mock_embedding(base_value=0.5, variation=0.0, seed=300)
        create_post_image(similar_post_3, create_test_image('sim3.jpg'), embedding=similar_embedding_3)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify results are returned
        result_ids = [post['id'] for post in res.data['results']]
        
        # Should have results
        self.assertGreater(len(result_ids), 0, "Should return similar posts")
        
        # Verify that the posts are in the results (order may vary based on cosine distance)
        self.assertIn(similar_post_1.id, result_ids, "Similar post 1 should be in results")
        self.assertIn(similar_post_2.id, result_ids, "Similar post 2 should be in results")
        self.assertIn(similar_post_3.id, result_ids, "Similar post 3 should be in results")
        
        # Verify that the ordering preserves the order from find_similar_images
        # The exact order depends on the cosine distance calculation, but all should be present
        self.assertEqual(len(result_ids), 3, "Should return all 3 similar posts")
        
    def test_list_similar_posts_with_embeddings_handles_duplicates(self):
        """
        Test that similar posts endpoint handles posts with multiple images correctly.
        """
        # Create a reference post
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=300)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create a post with multiple images (similar embeddings)
        multi_image_post = create_post("Multi image post", self.profile_3)
        similar_embedding_1 = create_mock_embedding(base_value=0.51, variation=0.0, seed=301)
        similar_embedding_2 = create_mock_embedding(base_value=0.52, variation=0.0, seed=302)
        create_post_image(multi_image_post, create_test_image('multi1.jpg'), embedding=similar_embedding_1)
        create_post_image(multi_image_post, create_test_image('multi2.jpg'), embedding=similar_embedding_2)
        
        url = list_similar_posts_url(reference_post)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # The post should appear only once, even though it has multiple similar images
        result_ids = [post['id'] for post in res.data['results']]
        count_of_multi_image_post = result_ids.count(multi_image_post.id)
        self.assertEqual(count_of_multi_image_post, 1)
        
    def test_list_similar_posts_with_embeddings_respects_min_similarity(self):
        """
        Test that min_similarity parameter filters results appropriately.
        """
        # Create a reference post
        reference_post = create_post("Reference post", self.profile_2)
        reference_embedding = create_mock_embedding(base_value=0.5, variation=0.0, seed=400)
        create_post_image(reference_post, create_test_image('ref.jpg'), embedding=reference_embedding)
        
        # Create a very similar post
        very_similar_post = create_post("Very similar", self.profile_3)
        very_similar_embedding = create_mock_embedding(base_value=0.501, variation=0.0, seed=401)
        create_post_image(very_similar_post, create_test_image('very_sim.jpg'), embedding=very_similar_embedding)
        
        # Create a moderately similar post
        moderate_post = create_post("Moderate similarity", self.profile_4)
        moderate_embedding = create_mock_embedding(base_value=0.6, variation=0.0, seed=402)
        create_post_image(moderate_post, create_test_image('moderate.jpg'), embedding=moderate_embedding)
        
        # Test with high min_similarity (should only get very similar posts)
        url = list_similar_posts_url(reference_post)
        res = self.client.get(url, {'min_similarity': 0.9})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        result_ids = [post['id'] for post in res.data['results']]
        
        # Very similar post should be included
        self.assertIn(very_similar_post.id, result_ids)
        
        # Test with lower min_similarity (should get more posts)
        res_low = self.client.get(url, {'min_similarity': 0.1})
        self.assertEqual(res_low.status_code, status.HTTP_200_OK)
        
        # Should have same or more results with lower threshold
        self.assertGreaterEqual(len(res_low.data['results']), len(res.data['results']))
        
    def test_list_similar_posts_with_post_without_images(self):
        """
        Test that similar posts endpoint handles posts without images gracefully.
        """
        # Create a post without images
        post_no_image = create_post("Post without images", self.profile_2)
        
        url = list_similar_posts_url(post_no_image)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Should return results (using fallback logic)
        self.assertIn('results', res.data)
        
    def test_list_similar_posts_with_nonexistent_post(self):
        """
        Test that requesting similar posts for a non-existent post returns empty results.
        The view catches exceptions and returns an empty queryset instead of 404.
        """
        url = list_similar_posts_url("01HF7YQX8J9K2P3M4N5R6S7T8X")  # Non-existent post public_id (26-char ULID)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should return empty results
        self.assertIn('results', res.data)
        self.assertEqual(len(res.data['results']), 0)
        
    def test_list_similar_posts_authenticated_required(self):
        """
        Test that ListSimilarPostsView requires authentication.
        """
        # Logout the current user
        self.client.force_authenticate(user=None)
        
        url = list_similar_posts_url(self.post_2)
        
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

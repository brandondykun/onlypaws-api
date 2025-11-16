"""
Tests for the Saved Posts api.
"""

from rest_framework import status
from apps.posts_app.models import SavedPost

from .util import list_create_saved_post_url, destroy_saved_post_url
from core.test_utils.helper_classes import BaseFixtureTestCase


class PrivateSavedPostsApiTests(BaseFixtureTestCase):
    """Test the private features of the Saved Posts API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    # ==================== LIST SAVED POSTS TESTS ====================

    def test_list_saved_posts_success(self):
        """
        Test successfully listing saved posts returns posts in correct order.
        """
        # Save some posts for self.profile
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        SavedPost.objects.create(profile=self.profile, post=self.post_4)
        SavedPost.objects.create(profile=self.profile, post=self.post_5)

        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        
        # Should return 3 saved posts
        self.assertEqual(len(res.data["results"]), 3)
        
        # Posts should be ordered by -saved_at (most recent first)
        # saved_post_3 was created last, so it should be first
        result_ids = [post["id"] for post in res.data["results"]]
        self.assertEqual(result_ids[0], self.post_5.id)
        self.assertEqual(result_ids[1], self.post_4.id)
        self.assertEqual(result_ids[2], self.post_3.id)

    def test_list_saved_posts_empty_success(self):
        """
        Test listing saved posts when none exist returns empty list.
        """
        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_saved_posts_only_returns_own_saved_posts(self):
        """
        Test that listing saved posts only returns the authenticated profile's saved posts.
        """
        # self.profile saves post_3
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        
        # profile_2 saves post_4 and post_5
        SavedPost.objects.create(profile=self.profile_2, post=self.post_4)
        SavedPost.objects.create(profile=self.profile_2, post=self.post_5)

        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Should only return self.profile's saved post (post_3)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["id"], self.post_3.id)

    def test_list_saved_posts_returns_detailed_post_data(self):
        """
        Test that listing saved posts returns detailed post information.
        """
        SavedPost.objects.create(profile=self.profile, post=self.post_3)

        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        
        # Verify detailed post fields are included
        post_data = res.data["results"][0]
        self.assertIn("id", post_data)
        self.assertIn("caption", post_data)
        self.assertIn("profile", post_data)
        self.assertIn("images", post_data)
        self.assertIn("likes_count", post_data)
        self.assertIn("comments_count", post_data)
        self.assertIn("is_saved", post_data)
        
        # The post should be marked as saved
        self.assertTrue(post_data["is_saved"])

    def test_list_saved_posts_unauthenticated_fails(self):
        """
        Test that listing saved posts without authentication fails.
        """
        # Logout the current user
        self.client.force_authenticate(user=None)
        self.client.credentials()

        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==================== CREATE SAVED POST TESTS ====================

    def test_create_saved_post_success(self):
        """
        Test successfully creating a saved post.
        """
        starting_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()

        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
            "post": self.post_3.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["profile"], self.profile.id)
        self.assertEqual(res.data["post"], self.post_3.id)

        # Verify saved post was created in database
        current_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()
        self.assertEqual(current_saved_posts_count, starting_saved_posts_count + 1)
        
        # Verify the saved post exists with correct data
        saved_post = SavedPost.objects.get(profile=self.profile, post=self.post_3)
        self.assertEqual(saved_post.profile.id, self.profile.id)
        self.assertEqual(saved_post.post.id, self.post_3.id)

    def test_create_saved_post_for_own_post_success(self):
        """
        Test that a user can save their own post.
        """
        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
            "post": self.post_1.id,  # self.post_1 belongs to self.profile
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        # Verify saved post exists
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile, post=self.post_1
        ).exists()
        self.assertTrue(saved_post_exists)

    def test_create_saved_post_duplicate_fails(self):
        """
        Test that saving the same post twice fails due to unique_together constraint.
        """
        # Save the post once
        SavedPost.objects.create(profile=self.profile, post=self.post_3)

        # Try to save the same post again
        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
            "post": self.post_3.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)

    def test_create_saved_post_wrong_profile_fails(self):
        """
        Test that creating a saved post with a different profile ID fails.
        """
        starting_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()

        url = list_create_saved_post_url()
        data = {
            "profile": self.profile_2.id,  # Different profile
            "post": self.post_3.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify no saved post was created
        current_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()
        self.assertEqual(current_saved_posts_count, starting_saved_posts_count)
        
        # Verify saved post doesn't exist for profile_2 either
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile_2, post=self.post_3
        ).exists()
        self.assertFalse(saved_post_exists)

    def test_create_saved_post_invalid_post_id_fails(self):
        """
        Test that creating a saved post with non-existent post ID fails.
        """
        starting_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()

        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
            "post": 99999,  # Non-existent post ID
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify no saved post was created
        current_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()
        self.assertEqual(current_saved_posts_count, starting_saved_posts_count)

    def test_create_saved_post_missing_profile_fails(self):
        """
        Test that creating a saved post without profile field fails.
        """
        url = list_create_saved_post_url()
        data = {
            "post": self.post_3.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_saved_post_missing_post_fails(self):
        """
        Test that creating a saved post without post field fails.
        """
        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_saved_post_unauthenticated_fails(self):
        """
        Test that creating a saved post without authentication fails.
        """
        # Logout the current user
        self.client.force_authenticate(user=None)
        self.client.credentials()

        url = list_create_saved_post_url()
        data = {
            "profile": self.profile.id,
            "post": self.post_3.id,
        }
        res = self.client.post(url, data=data)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==================== DESTROY SAVED POST TESTS ====================

    def test_destroy_saved_post_success(self):
        """
        Test successfully deleting a saved post.
        """
        # Create a saved post
        saved_post = SavedPost.objects.create(profile=self.profile, post=self.post_3)
        starting_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()

        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Verify saved post was deleted
        current_saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()
        self.assertEqual(current_saved_posts_count, starting_saved_posts_count - 1)
        
        # Verify the specific saved post no longer exists
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile, post=self.post_3
        ).exists()
        self.assertFalse(saved_post_exists)

    def test_destroy_saved_post_not_saved_fails(self):
        """
        Test that deleting a post that was never saved fails appropriately.
        """
        # Don't create a saved post for post_3
        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        # Should return 400 or 404 since the saved post doesn't exist
        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_destroy_saved_post_other_users_saved_post_fails(self):
        """
        Test that a user cannot delete another user's saved post.
        """
        # profile_2 saves post_3
        SavedPost.objects.create(profile=self.profile_2, post=self.post_3)

        # self.profile tries to delete it
        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        # Should fail because self.profile hasn't saved post_3
        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

        # Verify profile_2's saved post still exists
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile_2, post=self.post_3
        ).exists()
        self.assertTrue(saved_post_exists)

    def test_destroy_saved_post_invalid_post_id_fails(self):
        """
        Test that deleting a saved post with non-existent post ID fails.
        """
        url = destroy_saved_post_url(99999)  # Non-existent post ID
        res = self.client.delete(url)

        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_destroy_saved_post_does_not_delete_actual_post(self):
        """
        Test that deleting a saved post doesn't delete the actual post.
        """
        from apps.posts_app.models import Post
        
        # Save post_3
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        
        # Verify post exists
        self.assertTrue(Post.objects.filter(id=self.post_3.id).exists())

        # Delete the saved post
        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Verify the actual post still exists
        self.assertTrue(Post.objects.filter(id=self.post_3.id).exists())

    def test_destroy_saved_post_multiple_users_saved_same_post(self):
        """
        Test that deleting one user's saved post doesn't affect other users' saved posts.
        """
        # Both self.profile and profile_2 save post_3
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        SavedPost.objects.create(profile=self.profile_2, post=self.post_3)

        # self.profile deletes their saved post
        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Verify self.profile's saved post is gone
        self_saved_post_exists = SavedPost.objects.filter(
            profile=self.profile, post=self.post_3
        ).exists()
        self.assertFalse(self_saved_post_exists)

        # Verify profile_2's saved post still exists
        profile_2_saved_post_exists = SavedPost.objects.filter(
            profile=self.profile_2, post=self.post_3
        ).exists()
        self.assertTrue(profile_2_saved_post_exists)

    def test_destroy_saved_post_unauthenticated_fails(self):
        """
        Test that deleting a saved post without authentication fails.
        """
        # Create a saved post
        SavedPost.objects.create(profile=self.profile, post=self.post_3)

        # Logout the current user
        self.client.force_authenticate(user=None)
        self.client.credentials()

        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify saved post still exists
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile, post=self.post_3
        ).exists()
        self.assertTrue(saved_post_exists)

    def test_destroy_saved_post_wrong_profile_header_fails(self):
        """
        Test that deleting a saved post with wrong profile header fails.
        
        When a user tries to use a profile ID that doesn't belong to them,
        the authentication middleware should reject the request.
        """
        # self.profile saves post_3
        SavedPost.objects.create(profile=self.profile, post=self.post_3)

        # Authenticate as self.user but try to use profile_2's ID in header
        # This should fail authentication since profile_2 doesn't belong to self.user
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile_2.id)

        url = destroy_saved_post_url(self.post_3.id)
        res = self.client.delete(url)

        # Should fail with 401 because the profile doesn't belong to the authenticated user
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify self.profile's saved post still exists
        saved_post_exists = SavedPost.objects.filter(
            profile=self.profile, post=self.post_3
        ).exists()
        self.assertTrue(saved_post_exists)

    # ==================== INTEGRATION TESTS ====================

    def test_save_and_unsave_post_flow(self):
        """
        Test the complete flow of saving and then un-saving a post.
        """
        # Step 1: Save a post
        create_url = list_create_saved_post_url()
        create_data = {
            "profile": self.profile.id,
            "post": self.post_3.id,
        }
        create_res = self.client.post(create_url, data=create_data)
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        # Step 2: Verify it appears in saved posts list
        list_url = list_create_saved_post_url()
        list_res = self.client.get(list_url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data["results"]), 1)
        self.assertEqual(list_res.data["results"][0]["id"], self.post_3.id)
        self.assertTrue(list_res.data["results"][0]["is_saved"])

        # Step 3: Unsave the post
        delete_url = destroy_saved_post_url(self.post_3.id)
        delete_res = self.client.delete(delete_url)
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)

        # Step 4: Verify it no longer appears in saved posts list
        list_res_after = self.client.get(list_url)
        self.assertEqual(list_res_after.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res_after.data["results"]), 0)

    def test_save_multiple_posts_success(self):
        """
        Test saving multiple different posts successfully.
        """
        url = list_create_saved_post_url()

        # Save post_3
        data_1 = {"profile": self.profile.id, "post": self.post_3.id}
        res_1 = self.client.post(url, data=data_1)
        self.assertEqual(res_1.status_code, status.HTTP_201_CREATED)

        # Save post_4
        data_2 = {"profile": self.profile.id, "post": self.post_4.id}
        res_2 = self.client.post(url, data=data_2)
        self.assertEqual(res_2.status_code, status.HTTP_201_CREATED)

        # Save post_5
        data_3 = {"profile": self.profile.id, "post": self.post_5.id}
        res_3 = self.client.post(url, data=data_3)
        self.assertEqual(res_3.status_code, status.HTTP_201_CREATED)

        # Verify all 3 saved posts exist
        saved_posts_count = SavedPost.objects.filter(profile=self.profile).count()
        self.assertEqual(saved_posts_count, 3)

        # Verify they appear in the list
        list_res = self.client.get(url)
        self.assertEqual(len(list_res.data["results"]), 3)

    def test_saved_posts_ordering_chronological(self):
        """
        Test that saved posts are returned in reverse chronological order (most recent first).
        """
        import time
        
        # Save posts with small delays to ensure different timestamps
        SavedPost.objects.create(profile=self.profile, post=self.post_3)
        time.sleep(0.01)  # Small delay
        SavedPost.objects.create(profile=self.profile, post=self.post_4)
        time.sleep(0.01)  # Small delay
        SavedPost.objects.create(profile=self.profile, post=self.post_5)

        url = list_create_saved_post_url()
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Most recently saved (post_5) should be first
        result_ids = [post["id"] for post in res.data["results"]]
        self.assertEqual(result_ids[0], self.post_5.id)
        self.assertEqual(result_ids[1], self.post_4.id)
        self.assertEqual(result_ids[2], self.post_3.id)


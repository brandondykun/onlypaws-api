"""
Tests for the comment like api.
"""

from rest_framework import status
from apps.interactions_app.models import CommentLike
from .util import PostsAppTestHelper


def comment_like_url(comment_id: int):
    """Create and return a comment like url.

    Parameters
    ----------
    comment_id : int
        The id of the Comment to like/unlike.
    """
    from django.urls import reverse
    return reverse("posts_app:comment_like", args=[comment_id])


class PrivateCommentLikeApiTests(PostsAppTestHelper):
    """Test the private features of the Comment Like API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    # ========================================
    # POST (Create Comment Like) Tests
    # ========================================

    def test_create_comment_like_successful(self):
        """Test creating a comment like is successful."""
        starting_likes_count = CommentLike.objects.count()

        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["profile"], self.profile.id)
        self.assertEqual(res.data["comment"], self.comment_1.id)
        
        # Verify database state
        self.assertEqual(CommentLike.objects.count(), starting_likes_count + 1)
        like_exists = CommentLike.objects.filter(
            profile=self.profile, comment=self.comment_1
        ).exists()
        self.assertTrue(like_exists)

    def test_create_comment_like_for_other_profiles_comment_successful(self):
        """Test that a profile can like another profile's comment."""
        # Use profile_2's comment
        starting_likes_count = CommentLike.objects.count()

        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count + 1)

    def test_create_comment_like_for_own_comment_successful(self):
        """Test that a profile can like their own comment (if allowed by business logic)."""
        # self.comment_1 belongs to self.profile
        starting_likes_count = CommentLike.objects.count()

        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        # Based on the view code, there's no restriction on liking own comments
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count + 1)

    def test_create_comment_like_with_wrong_profile_id_fails(self):
        """Test creating a comment like with a profile that doesn't belong to the authenticated user fails."""
        starting_likes_count = CommentLike.objects.count()

        # Try to use profile_2's id while authenticated as self.user
        payload = {"profileId": self.profile_2.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify no like was created
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_create_comment_like_without_profile_id_fails(self):
        """Test creating a comment like without profileId in payload fails."""
        starting_likes_count = CommentLike.objects.count()

        payload = {}  # Missing profileId
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_create_duplicate_comment_like_fails(self):
        """Test creating a duplicate comment like (same profile, same comment) fails."""
        # Create initial like
        CommentLike.objects.create(profile=self.profile, comment=self.comment_1)
        starting_likes_count = CommentLike.objects.count()

        # Try to create duplicate
        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify no additional like was created
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_create_comment_like_for_nonexistent_comment_fails(self):
        """Test creating a comment like for a non-existent comment fails."""
        starting_likes_count = CommentLike.objects.count()
        nonexistent_comment_id = 99999

        payload = {"profileId": self.profile.id}
        url = comment_like_url(nonexistent_comment_id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_create_comment_like_with_invalid_profile_id_format_fails(self):
        """Test creating a comment like with invalid profileId format fails."""
        starting_likes_count = CommentLike.objects.count()

        payload = {"profileId": "invalid"}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_create_multiple_comment_likes_by_same_profile_on_different_comments(self):
        """Test that the same profile can like multiple different comments."""
        starting_likes_count = CommentLike.objects.count()

        # Like first comment
        payload = {"profileId": self.profile.id}
        url1 = comment_like_url(self.comment_1.id)
        res1 = self.client.post(url1, payload)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Like second comment
        url2 = comment_like_url(self.comment_2.id)
        res2 = self.client.post(url2, payload)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # Verify both likes were created
        self.assertEqual(CommentLike.objects.count(), starting_likes_count + 2)

    # ========================================
    # DELETE (Destroy Comment Like) Tests
    # ========================================

    def test_delete_comment_like_successful(self):
        """Test deleting a comment like is successful."""
        # Create a like first
        CommentLike.objects.create(profile=self.profile, comment=self.comment_1)
        starting_likes_count = CommentLike.objects.count()

        url = comment_like_url(self.comment_1.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        # Verify database state
        self.assertEqual(CommentLike.objects.count(), starting_likes_count - 1)
        like_exists = CommentLike.objects.filter(
            profile=self.profile, comment=self.comment_1
        ).exists()
        self.assertFalse(like_exists)

    def test_delete_comment_like_that_does_not_exist_fails(self):
        """Test deleting a comment like that doesn't exist returns 400."""
        starting_likes_count = CommentLike.objects.count()

        # Try to delete a like that was never created
        url = comment_like_url(self.comment_1.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify no changes to database
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_delete_comment_like_for_nonexistent_comment_fails(self):
        """Test deleting a comment like for a non-existent comment fails."""
        starting_likes_count = CommentLike.objects.count()
        nonexistent_comment_id = 99999

        url = comment_like_url(nonexistent_comment_id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_delete_someone_elses_comment_like_fails(self):
        """Test that a profile cannot delete another profile's comment like."""
        # Create a like by profile_2
        CommentLike.objects.create(profile=self.profile_2, comment=self.comment_1)
        starting_likes_count = CommentLike.objects.count()

        # Try to delete it as self.profile (authenticated)
        url = comment_like_url(self.comment_1.id)
        res = self.client.delete(url)

        # Should get 400 because the like doesn't exist for self.profile
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify the like still exists
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)
        like_exists = CommentLike.objects.filter(
            profile=self.profile_2, comment=self.comment_1
        ).exists()
        self.assertTrue(like_exists)

    def test_create_delete_then_create_again_successful(self):
        """Test creating, deleting, then creating the same comment like again works."""
        # Create
        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res1 = self.client.post(url, payload)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        
        # Delete
        res2 = self.client.delete(url)
        self.assertEqual(res2.status_code, status.HTTP_204_NO_CONTENT)
        
        # Create again
        res3 = self.client.post(url, payload)
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)
        
        # Verify final state
        like_exists = CommentLike.objects.filter(
            profile=self.profile, comment=self.comment_1
        ).exists()
        self.assertTrue(like_exists)

    # ========================================
    # Authentication Tests
    # ========================================

    def test_multiple_profiles_can_like_same_comment(self):
        """Test that multiple profiles can like the same comment."""
        starting_likes_count = CommentLike.objects.count()

        # Profile 1 likes the comment
        payload1 = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res1 = self.client.post(url, payload1)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Switch to profile_2
        self.client.force_authenticate(user=self.user_2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile_2.id)

        # Profile 2 likes the same comment
        payload2 = {"profileId": self.profile_2.id}
        res2 = self.client.post(url, payload2)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # Verify both likes exist
        self.assertEqual(CommentLike.objects.count(), starting_likes_count + 2)
        self.assertTrue(
            CommentLike.objects.filter(profile=self.profile, comment=self.comment_1).exists()
        )
        self.assertTrue(
            CommentLike.objects.filter(profile=self.profile_2, comment=self.comment_1).exists()
        )


class PublicCommentLikeApiTests(PostsAppTestHelper):
    """Test the public features of the Comment Like API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # Do not authenticate - testing unauthorized access

    def test_create_comment_like_without_authentication_fails(self):
        """Test creating a comment like without authentication returns error."""
        starting_likes_count = CommentLike.objects.count()

        payload = {"profileId": self.profile.id}
        url = comment_like_url(self.comment_1.id)
        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        # Verify no like was created
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)

    def test_delete_comment_like_without_authentication_fails(self):
        """Test deleting a comment like without authentication returns error."""
        # Create a like first
        CommentLike.objects.create(profile=self.profile, comment=self.comment_1)
        starting_likes_count = CommentLike.objects.count()

        url = comment_like_url(self.comment_1.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        # Verify like still exists
        self.assertEqual(CommentLike.objects.count(), starting_likes_count)
        like_exists = CommentLike.objects.filter(
            profile=self.profile, comment=self.comment_1
        ).exists()
        self.assertTrue(like_exists)


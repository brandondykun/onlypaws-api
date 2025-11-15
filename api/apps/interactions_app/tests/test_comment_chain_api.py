"""
Tests for the comment chain retrieval API.
"""

from rest_framework import status

from .util import comment_chain_url
from core.test_utils.utils import create_comment
from core.test_utils.helper_classes import BaseFixtureTestCase


class PrivateCommentChainApiTests(BaseFixtureTestCase):
    """Test the private features of the Comment Chain API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_retrieve_top_level_comment_chain_successful(self):
        """Test retrieving a top-level comment (no parents) returns correct structure."""
        # Create a top-level comment
        comment = create_comment(
            profile=self.profile,
            text="Top level comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )

        url = comment_chain_url(comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify response structure
        self.assertIn("post", res.data)
        self.assertIn("target_comment", res.data)
        self.assertIn("root_parent_comment", res.data)
        self.assertIn("parent_chain", res.data)
        self.assertIn("omitted_count", res.data)
        
        # Verify target comment
        self.assertEqual(res.data["target_comment"]["id"], comment.id)
        self.assertEqual(res.data["target_comment"]["text"], comment.text)
        self.assertEqual(res.data["target_comment"]["parent_comment"], None)
        self.assertEqual(res.data["target_comment"]["reply_to_comment"], None)
        
        # No parent chain for top-level comment
        self.assertIsNone(res.data["root_parent_comment"])
        self.assertEqual(len(res.data["parent_chain"]), 0)
        self.assertEqual(res.data["omitted_count"], 0)
        
        # Verify post is included
        self.assertEqual(res.data["post"]["id"], self.post_1.id)

    def test_retrieve_comment_with_single_parent_successful(self):
        """Test retrieving a comment with one parent returns correct parent chain."""
        # Create parent comment
        parent_comment = create_comment(
            profile=self.profile_2,
            text="Parent comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        
        # Create child comment
        child_comment = create_comment(
            profile=self.profile,
            text="Child comment",
            post=self.post_1,
            parent_comment=parent_comment,
            reply_to_comment=parent_comment,
        )

        url = comment_chain_url(child_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify target comment
        self.assertEqual(res.data["target_comment"]["id"], child_comment.id)
        self.assertEqual(res.data["target_comment"]["text"], child_comment.text)
        self.assertEqual(res.data["target_comment"]["parent_comment"], parent_comment.id)
        self.assertEqual(res.data["target_comment"]["reply_to_comment"], parent_comment.id)
        self.assertEqual(
            res.data["target_comment"]["reply_to_comment_username"],
            parent_comment.profile.username
        )
        
        # Verify root parent
        self.assertIsNotNone(res.data["root_parent_comment"])
        self.assertEqual(res.data["root_parent_comment"]["id"], parent_comment.id)
        self.assertEqual(res.data["root_parent_comment"]["text"], parent_comment.text)
        
        # No intermediate ancestors (only root and target)
        self.assertEqual(len(res.data["parent_chain"]), 0)
        self.assertEqual(res.data["omitted_count"], 0)

    def test_retrieve_comment_with_multiple_parents_successful(self):
        """Test retrieving a comment with multiple parents returns full chain."""
        # Create a chain: root -> middle1 -> middle2 -> target
        root_comment = create_comment(
            profile=self.profile_2,
            text="Root comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        
        middle1_comment = create_comment(
            profile=self.profile,
            text="Middle comment 1",
            post=self.post_1,
            parent_comment=root_comment,
            reply_to_comment=root_comment,
        )
        
        middle2_comment = create_comment(
            profile=self.profile_2,
            text="Middle comment 2",
            post=self.post_1,
            parent_comment=root_comment,
            reply_to_comment=middle1_comment,
        )
        
        target_comment = create_comment(
            profile=self.profile,
            text="Target comment",
            post=self.post_1,
            parent_comment=root_comment,
            reply_to_comment=middle2_comment,
        )

        url = comment_chain_url(target_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify target comment
        self.assertEqual(res.data["target_comment"]["id"], target_comment.id)
        self.assertEqual(res.data["target_comment"]["text"], target_comment.text)
        
        # Verify root parent
        self.assertIsNotNone(res.data["root_parent_comment"])
        self.assertEqual(res.data["root_parent_comment"]["id"], root_comment.id)
        
        # Verify parent chain contains intermediate ancestors (excluding root)
        self.assertEqual(len(res.data["parent_chain"]), 2)
        self.assertEqual(res.data["parent_chain"][0]["id"], middle1_comment.id)
        self.assertEqual(res.data["parent_chain"][1]["id"], middle2_comment.id)
        
        # No omitted comments
        self.assertEqual(res.data["omitted_count"], 0)

    def test_retrieve_comment_with_deep_chain_shows_last_10(self):
        """Test retrieving a comment with >10 parents shows only last 10 in chain."""
        # Create a chain of 15 comments: root -> 1 -> 2 -> ... -> 14 (target)
        comments = []
        
        # Root comment
        root_comment = create_comment(
            profile=self.profile,
            text="Root comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        comments.append(root_comment)
        
        # Create 13 intermediate comments (1-13)
        for i in range(1, 14):
            new_comment = create_comment(
                profile=self.profile if i % 2 == 0 else self.profile_2,
                text=f"Comment {i}",
                post=self.post_1,
                parent_comment=root_comment,
                reply_to_comment=comments[i-1],
            )
            comments.append(new_comment)
        
        # Target comment (14th in chain)
        target_comment = create_comment(
            profile=self.profile,
            text="Target comment",
            post=self.post_1,
            parent_comment=root_comment,
            reply_to_comment=comments[-1],
        )

        url = comment_chain_url(target_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify target comment
        self.assertEqual(res.data["target_comment"]["id"], target_comment.id)
        
        # Verify root parent
        self.assertEqual(res.data["root_parent_comment"]["id"], root_comment.id)
        
        # Should have exactly 10 in parent_chain (excluding root)
        # Total ancestors = 14 (root + 13 intermediate)
        # Excluding root = 13
        # Last 10 of those 13 = comments[4:14] (index 4-13)
        self.assertEqual(len(res.data["parent_chain"]), 10)
        
        # Verify it shows the LAST 10 intermediate comments (excluding root)
        # That would be comments 4-13
        for i, parent in enumerate(res.data["parent_chain"]):
            expected_comment = comments[4 + i]
            self.assertEqual(parent["id"], expected_comment.id)
            self.assertEqual(parent["text"], expected_comment.text)
        
        # Omitted count should be 3 (comments 1, 2, 3)
        self.assertEqual(res.data["omitted_count"], 3)

    def test_retrieve_comment_with_exact_10_parents(self):
        """Test retrieving a comment with exactly 10 intermediate parents (11 total)."""
        # Create chain: root + 10 intermediate + target = 12 total
        comments = []
        
        root_comment = create_comment(
            profile=self.profile,
            text="Root comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        comments.append(root_comment)
        
        # Create exactly 10 intermediate comments
        for i in range(1, 11):
            new_comment = create_comment(
                profile=self.profile if i % 2 == 0 else self.profile_2,
                text=f"Comment {i}",
                post=self.post_1,
                parent_comment=root_comment,
                reply_to_comment=comments[i-1],
            )
            comments.append(new_comment)
        
        target_comment = create_comment(
            profile=self.profile,
            text="Target comment",
            post=self.post_1,
            parent_comment=root_comment,
            reply_to_comment=comments[-1],
        )

        url = comment_chain_url(target_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # All 10 intermediate ancestors should be in parent_chain
        self.assertEqual(len(res.data["parent_chain"]), 10)
        
        # No comments omitted
        self.assertEqual(res.data["omitted_count"], 0)
        
        # Verify all intermediate comments are present in order
        for i, parent in enumerate(res.data["parent_chain"]):
            expected_comment = comments[i + 1]  # Skip root (index 0)
            self.assertEqual(parent["id"], expected_comment.id)

    def test_retrieve_comment_includes_likes_count_and_liked_status(self):
        """Test that comment chain includes likes_count and liked status for each comment."""
        from apps.interactions_app.models import CommentLike
        
        # Create parent and child comments
        parent_comment = create_comment(
            profile=self.profile_2,
            text="Parent comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        
        child_comment = create_comment(
            profile=self.profile,
            text="Child comment",
            post=self.post_1,
            parent_comment=parent_comment,
            reply_to_comment=parent_comment,
        )
        
        # Add likes to parent comment
        CommentLike.objects.create(profile=self.profile, comment=parent_comment)
        CommentLike.objects.create(profile=self.profile_2, comment=parent_comment)
        
        # Add like to child comment (by current user)
        CommentLike.objects.create(profile=self.profile, comment=child_comment)

        url = comment_chain_url(child_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify target comment likes
        self.assertEqual(res.data["target_comment"]["likes_count"], 1)
        self.assertTrue(res.data["target_comment"]["liked"])
        
        # Verify parent comment likes
        self.assertEqual(res.data["root_parent_comment"]["likes_count"], 2)
        self.assertTrue(res.data["root_parent_comment"]["liked"])

    def test_retrieve_comment_includes_profile_data(self):
        """Test that comment chain includes full profile data for each comment."""
        parent_comment = create_comment(
            profile=self.profile_2,
            text="Parent comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        
        child_comment = create_comment(
            profile=self.profile,
            text="Child comment",
            post=self.post_1,
            parent_comment=parent_comment,
            reply_to_comment=parent_comment,
        )

        url = comment_chain_url(child_comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify target comment has profile data
        target_profile = res.data["target_comment"]["profile"]
        self.assertEqual(target_profile["id"], self.profile.id)
        self.assertEqual(target_profile["username"], self.profile.username)
        
        # Verify root parent has profile data
        root_profile = res.data["root_parent_comment"]["profile"]
        self.assertEqual(root_profile["id"], self.profile_2.id)
        self.assertEqual(root_profile["username"], self.profile_2.username)

    def test_retrieve_nonexistent_comment_returns_404(self):
        """Test retrieving a non-existent comment returns 404."""
        url = comment_chain_url(99999)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_comment_chain_verifies_comment_ordering(self):
        """Test that parent chain is ordered from oldest to newest (immediate parent)."""
        # Create chain: root -> c1 -> c2 -> c3 -> target
        root = create_comment(
            profile=self.profile,
            text="Root",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )
        
        c1 = create_comment(
            profile=self.profile_2,
            text="Comment 1",
            post=self.post_1,
            parent_comment=root,
            reply_to_comment=root,
        )
        
        c2 = create_comment(
            profile=self.profile,
            text="Comment 2",
            post=self.post_1,
            parent_comment=root,
            reply_to_comment=c1,
        )
        
        c3 = create_comment(
            profile=self.profile_2,
            text="Comment 3",
            post=self.post_1,
            parent_comment=root,
            reply_to_comment=c2,
        )
        
        target = create_comment(
            profile=self.profile,
            text="Target",
            post=self.post_1,
            parent_comment=root,
            reply_to_comment=c3,
        )

        url = comment_chain_url(target.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Parent chain should be [c1, c2, c3] in that order
        self.assertEqual(len(res.data["parent_chain"]), 3)
        self.assertEqual(res.data["parent_chain"][0]["id"], c1.id)
        self.assertEqual(res.data["parent_chain"][1]["id"], c2.id)
        self.assertEqual(res.data["parent_chain"][2]["id"], c3.id)
        
        # Verify timestamps are in ascending order (oldest to newest)
        timestamps = [comment["created_at"] for comment in res.data["parent_chain"]]
        self.assertEqual(timestamps, sorted(timestamps))


class PublicCommentChainApiTests(BaseFixtureTestCase):
    """Test the public features of the Comment Chain API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_retrieve_comment_chain_without_authentication_returns_error(self):
        """Test retrieving comment chain without authentication returns 401."""
        # Create a comment
        comment = create_comment(
            profile=self.profile,
            text="Test comment",
            post=self.post_1,
            parent_comment=None,
            reply_to_comment=None,
        )

        url = comment_chain_url(comment.id)
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


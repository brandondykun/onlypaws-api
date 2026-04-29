"""
Tests for the recommendable_posts_qs helper.
"""

from apps.moderation_app.models import PostReport
from apps.posts_app.models import Post
from apps.recommendations_app.queryset_utils import recommendable_posts_qs
from core.test_utils.helper_classes import BaseFixtureTestCase


class RecommendablePostsQsTests(BaseFixtureTestCase):

    def setUp(self):
        super().setUp()
        for post in (
            self.post_2,
            self.post_3,
            self.post_5,
            self.post_6,
            self.post_7,
            self.post_8,
        ):
            post.status = Post.Status.READY
            post.save(update_fields=["status"])

    def test_excludes_inappropriate_reported_posts(self):
        # post_1 and post_4 are reported with "Inappropriate Content" via fixture.
        ids = set(recommendable_posts_qs().values_list("id", flat=True))
        self.assertNotIn(self.post_1.id, ids)
        self.assertNotIn(self.post_4.id, ids)

    def test_excludes_non_ready_posts(self):
        self.post_5.status = Post.Status.PROCESSING
        self.post_5.save(update_fields=["status"])
        ids = set(recommendable_posts_qs().values_list("id", flat=True))
        self.assertNotIn(self.post_5.id, ids)

    def test_excludes_private_profile_posts(self):
        self.profile_3.is_private = True
        self.profile_3.save(update_fields=["is_private"])
        ids = set(recommendable_posts_qs().values_list("id", flat=True))
        self.assertNotIn(self.post_5.id, ids)
        self.assertNotIn(self.post_6.id, ids)

    def test_includes_posts_reported_only_for_non_inappropriate_reasons(self):
        # Policy choice: only INAPPROPRIATE reports gate eligibility. Reports
        # under "Not Pet Related" / "Other" do not hide a post from Explore;
        # those are handled by the heavily-reported-profile threshold instead.
        PostReport.objects.create(
            post=self.post_5, reporter=self.user_4, reason=self.reason2
        )
        ids = set(recommendable_posts_qs().values_list("id", flat=True))
        self.assertIn(self.post_5.id, ids)

    def test_eligible_post_is_returned(self):
        ids = set(recommendable_posts_qs().values_list("id", flat=True))
        self.assertIn(self.post_5.id, ids)

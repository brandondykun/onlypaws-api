"""
Helper classes for all test cases.
"""

from rest_framework.test import APIClient
from django.test import TestCase
from apps.posts_app.models import Post
from apps.interactions_app.models import Like, Follow
from apps.moderation_app.models import ReportReason, PostReport

from core.test_utils.utils import create_user, create_profile, create_post, create_follow, create_comment, create_post_image, create_test_image


class BaseFixtureTestCase(TestCase):
    """
    Base fixture test case helper class.
    Creates 4 user/profile combinations with 2 posts each.
    self.profile follows profile_2 leaving profile_3 and profile_4 un-followed.
    Create 2 comments for post_1.

    setUp() method does not authenticate a user. To authenticate a user add the
    following in the setUp() method of the child class:

    self.client.force_authenticate(user=self.user)
    self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)
    """

    @classmethod
    def setUpClass(cls):
        """Clear in-memory storage before running tests."""
        super().setUpClass()
        # Clear in-memory storage to ensure clean state
        try:
            from core.storage import InMemoryStorage
            InMemoryStorage.clear()
        except ImportError:
            # Storage backend not configured for tests
            pass

    def setUp(self):
        # Profile 1
        self.user = create_user("test@example.com", "user1-password-123", is_staff=True)
        self.profile = create_profile("username_1", self.user, "About text 1.")
        self.post_1 = create_post("Post 1 caption", self.profile)
        self.post_2 = create_post("Post 2 caption", self.profile)
        # Profile 2
        self.user_2 = create_user("test2@example.com", "user2-password-123")
        self.profile_2 = create_profile("username_2", self.user_2, "About text 2.")
        self.post_3 = create_post("Post 3 caption", self.profile_2)
        self.post_4 = create_post("Post 4 caption", self.profile_2)
        # Profile 3
        self.user_3 = create_user("test3@example.com", "user3-password-123")
        self.profile_3 = create_profile("username_3", self.user_3, "About text 3.")
        self.post_5 = create_post("Post 5 caption", self.profile_3)
        self.post_6 = create_post("Post 6 caption", self.profile_3)
        # Profile 4
        self.user_4 = create_user("test4@example.com", "user4-password-123")
        self.profile_4 = create_profile("username_4", self.user_4, "About text 4.")
        self.post_7 = create_post("Post 7 caption", self.profile_4)
        self.post_8 = create_post("Post 8 caption", self.profile_4)

        # self.profile follows profile 2
        self.follow = create_follow(self.profile, self.profile_2)

        # create 2 comments for post_1
        self.comment_1 = create_comment(self.profile, "Comment One", self.post_1)
        self.comment_2 = create_comment(self.profile, "Comment Two", self.post_1)

        # Create report reasons
        self.reason1 = ReportReason.objects.create(
            name="Inappropriate Content",
            description="Content contains inappropriate, offensive, or explicit material",
        )
        self.reason2 = ReportReason.objects.create(
            name="Not Pet Related", description="Content is not pet related"
        )
        self.reason3 = ReportReason.objects.create(
            name="Too Much Human",
            description="Content contains too much human presence and I'm not here for that",
        )
        self.reason4 = ReportReason.objects.create(
            name="Other",
            description="A reason other than the ones listed",
        )

        self.report1 = PostReport.objects.create(
            post=self.post_4, reporter=self.user, reason=self.reason1
        )
        self.report2 = PostReport.objects.create(
            post=self.post_1, reporter=self.user_2, reason=self.reason1
        )

        # Add images to posts for testing similar posts functionality
        # Post 1 - has image (reported post)
        self.post_1_image = create_post_image(self.post_1, create_test_image('post_1_image.jpg', color='red'))
        # Post 2 - has image
        self.post_2_image = create_post_image(self.post_2, create_test_image('post_2_image.jpg', color='blue'))
        # Post 3 - has image
        self.post_3_image = create_post_image(self.post_3, create_test_image('post_3_image.jpg', color='green'))
        # Post 4 - has image (reported post)
        self.post_4_image = create_post_image(self.post_4, create_test_image('post_4_image.jpg', color='yellow'))
        # Post 5 - has image
        self.post_5_image = create_post_image(self.post_5, create_test_image('post_5_image.jpg', color='purple'))
        # Post 6 - has image
        self.post_6_image = create_post_image(self.post_6, create_test_image('post_6_image.jpg', color='orange'))

        self.client = APIClient()

    def get_follows_count(self):
        """Get and return the number of Follows in the database."""
        return len(Follow.objects.all())

    def get_likes_count(self):
        """Get and return the number of Likes in the database."""
        return len(Like.objects.all())

    def get_posts_count(self):
        """Get and return the number of Posts in the database."""
        return len(Post.objects.all())

"""
Tests for post image blurhash generation and exposure.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from PIL import Image

from apps.core_app.image_placeholders import generate_blurhash_from_image
from apps.posts_app.models import Post, PostImage
from apps.posts_app.serializers import (
    PostDetailedSerializer,
    PostImageSerializer,
    PostSerializer,
)
from apps.posts_app.tasks import backfill_missing_blurhashes_task
from core.test_utils.utils import create_post, create_profile, create_user


class BlurhashHelperTests(SimpleTestCase):
    """Tests for blurhash helper functions."""

    def test_generate_blurhash_from_image_downscales_copy(self):
        image = Image.new("RGB", (150, 150), color="red")

        image_blurhash = generate_blurhash_from_image(image)

        self.assertIsInstance(image_blurhash, str)
        # 7x7 components encodes to a 102-char string.
        self.assertEqual(len(image_blurhash), 102)
        self.assertEqual(image.size, (150, 150))


class PostImageBlurhashSerializerTests(TestCase):
    """Tests for exposing blurhash values in the post image serializer."""

    def setUp(self):
        self.user = create_user("blurhash@example.com")
        self.profile = create_profile("blurhash-pet", self.user)

    def test_post_image_serializer_includes_blurhash(self):
        post = create_post("Post with blurhash", self.profile)
        image = PostImage.objects.create(
            post=post, order=0, blurhash="LKO2?U%2Tw=w]~RBVZRi};RPxuwH"
        )

        data = PostImageSerializer(image).data

        self.assertEqual(data["blurhash"], image.blurhash)

    def test_post_image_serializer_marks_blurhash_read_only(self):
        self.assertIn("blurhash", PostImageSerializer.Meta.fields)
        self.assertIn("blurhash", PostImageSerializer.Meta.read_only_fields)

    def test_post_serializers_no_longer_expose_post_level_blurhash(self):
        self.assertNotIn("blurhash", PostSerializer.Meta.fields)
        self.assertNotIn("blurhash", PostDetailedSerializer.Meta.fields)


class GeneratePostBlurhashesCommandTests(TestCase):
    """Tests for the generate_post_blurhashes management command."""

    def setUp(self):
        self.user = create_user("blurhash-command@example.com")
        self.profile = create_profile("blurhash-command-pet", self.user)

    @patch(
        "apps.core_app.management.commands.generate_post_blurhashes."
        "generate_blurhash_for_post_image"
    )
    def test_command_generates_blurhash_for_each_image(self, mock_generate):
        mock_generate.return_value = "LKO2?U%2Tw=w]~RBVZRi};RPxuwH"
        post = create_post("Needs blurhash", self.profile)
        first_image = PostImage.objects.create(post=post, order=0)
        second_image = PostImage.objects.create(post=post, order=1)

        call_command("generate_post_blurhashes", stdout=StringIO())

        first_image.refresh_from_db()
        second_image.refresh_from_db()
        self.assertEqual(first_image.blurhash, mock_generate.return_value)
        self.assertEqual(second_image.blurhash, mock_generate.return_value)
        self.assertEqual(mock_generate.call_count, 2)

    @patch(
        "apps.core_app.management.commands.generate_post_blurhashes."
        "generate_blurhash_for_post_image"
    )
    def test_command_skips_existing_blurhash_without_force(self, mock_generate):
        post = create_post("Already has blurhash", self.profile)
        PostImage.objects.create(post=post, order=0, blurhash="existing")

        call_command("generate_post_blurhashes", stdout=StringIO())

        mock_generate.assert_not_called()

    @patch(
        "apps.core_app.management.commands.generate_post_blurhashes."
        "generate_blurhash_for_post_image"
    )
    def test_command_regenerates_existing_blurhash_with_force(self, mock_generate):
        mock_generate.return_value = "LKO2?U%2Tw=w]~RBVZRi};RPxuwH"
        post = create_post("Force blurhash", self.profile)
        image = PostImage.objects.create(post=post, order=0, blurhash="existing")

        call_command("generate_post_blurhashes", "--force", stdout=StringIO())

        image.refresh_from_db()
        self.assertEqual(image.blurhash, mock_generate.return_value)
        mock_generate.assert_called_once_with(image)

    @patch(
        "apps.core_app.management.commands.generate_post_blurhashes."
        "generate_blurhash_for_post_image"
    )
    def test_command_dry_run_does_not_save_blurhash(self, mock_generate):
        post = create_post("Dry run blurhash", self.profile)
        image = PostImage.objects.create(post=post, order=0)

        call_command("generate_post_blurhashes", "--dry-run", stdout=StringIO())

        image.refresh_from_db()
        self.assertEqual(image.blurhash, "")
        mock_generate.assert_not_called()


class BackfillMissingBlurhashesTaskTests(TestCase):
    """Tests for the periodic blurhash backfill safety-net task."""

    BLURHASH = "LKO2?U%2Tw=w]~RBVZRi};RPxuwH"

    def setUp(self):
        self.user = create_user("blurhash-task@example.com")
        self.profile = create_profile("blurhash-task-pet", self.user)

    def _set_age(self, post, minutes):
        # created_at uses auto_now_add, so bypass it with a direct UPDATE.
        Post.objects.filter(pk=post.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes)
        )

    @patch("apps.posts_app.tasks.generate_blurhash_for_post_image")
    def test_backfills_images_on_old_ready_post(self, mock_generate):
        mock_generate.return_value = self.BLURHASH
        post = create_post("Needs blurhash", self.profile)
        first_image = PostImage.objects.create(post=post, order=0)
        second_image = PostImage.objects.create(post=post, order=1)
        self._set_age(post, 15)

        result = backfill_missing_blurhashes_task()

        first_image.refresh_from_db()
        second_image.refresh_from_db()
        self.assertEqual(first_image.blurhash, self.BLURHASH)
        self.assertEqual(second_image.blurhash, self.BLURHASH)
        self.assertEqual(result["processed"], 2)

    @patch("apps.posts_app.tasks.generate_blurhash_for_post_image")
    def test_skips_images_on_post_newer_than_min_age(self, mock_generate):
        post = create_post("Too new", self.profile)
        image = PostImage.objects.create(post=post, order=0)
        self._set_age(post, 5)  # younger than the 10 minute cutoff

        result = backfill_missing_blurhashes_task()

        image.refresh_from_db()
        self.assertEqual(image.blurhash, "")
        mock_generate.assert_not_called()
        self.assertEqual(result["candidates"], 0)

    @patch("apps.posts_app.tasks.generate_blurhash_for_post_image")
    def test_skips_image_with_existing_blurhash(self, mock_generate):
        post = create_post("Already set", self.profile)
        image = PostImage.objects.create(post=post, order=0, blurhash="existing")
        self._set_age(post, 15)

        backfill_missing_blurhashes_task()

        image.refresh_from_db()
        self.assertEqual(image.blurhash, "existing")
        mock_generate.assert_not_called()

    @patch("apps.posts_app.tasks.generate_blurhash_for_post_image")
    def test_skips_images_on_non_ready_post(self, mock_generate):
        post = create_post("Still processing", self.profile)
        post.status = Post.Status.PROCESSING
        post.save(update_fields=["status"])
        image = PostImage.objects.create(post=post, order=0)
        self._set_age(post, 15)

        backfill_missing_blurhashes_task()

        image.refresh_from_db()
        self.assertEqual(image.blurhash, "")
        mock_generate.assert_not_called()

    @patch("apps.posts_app.tasks.generate_blurhash_for_post_image")
    def test_respects_max_images_limit(self, mock_generate):
        mock_generate.return_value = self.BLURHASH
        for index in range(3):
            post = create_post(f"Needs blurhash {index}", self.profile)
            PostImage.objects.create(post=post, order=0)
            self._set_age(post, 15)

        result = backfill_missing_blurhashes_task(max_images=2)

        self.assertEqual(result["candidates"], 2)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(mock_generate.call_count, 2)

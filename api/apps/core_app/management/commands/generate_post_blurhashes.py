"""
Management command to generate blurhash placeholders for existing post images.
"""

from django.core.management.base import BaseCommand

from apps.core_app.image_placeholders import generate_blurhash_for_post_image
from apps.posts_app.models import Post, PostImage


class Command(BaseCommand):
    help = "Generate blurhash placeholders for post images that don't have them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without saving blurhashes.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate blurhashes even if they already exist.",
        )
        parser.add_argument(
            "--post-id",
            type=int,
            help="Process only images belonging to a specific post ID.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of images to process in each batch (default: 50).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        post_id = options.get("post_id")
        batch_size = options["batch_size"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE ===\n"))

        queryset = PostImage.objects.filter(post__status=Post.Status.READY)

        if post_id:
            queryset = queryset.filter(post_id=post_id)

        if not force:
            queryset = queryset.filter(blurhash="")

        image_ids = list(queryset.order_by("id").values_list("id", flat=True))
        total_count = len(image_ids)
        self.stdout.write(f"Found {total_count} images to process.\n")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No images need blurhash generation."))
            return

        processed_count = 0
        skipped_count = 0
        error_count = 0

        for start in range(0, total_count, batch_size):
            batch_ids = image_ids[start : start + batch_size]
            images = (
                PostImage.objects.filter(id__in=batch_ids)
                .prefetch_related("scaled_images")
                .order_by("id")
            )

            for image in images:
                try:
                    result = self._process_image(image, dry_run, force)
                    if result == "processed":
                        processed_count += 1
                    elif result == "skipped":
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Error processing PostImage {image.id}: {e}")
                    )

            self.stdout.write(
                f"Progress: {min(start + batch_size, total_count)}/{total_count}"
            )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Processed: {processed_count}"))
        self.stdout.write(f"Skipped: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN - No changes made ==="))

    def _process_image(self, image, dry_run, force):
        """Generate and persist a blurhash for a single PostImage."""
        self.stdout.write(f"Processing PostImage {image.id}")

        if image.blurhash and not force:
            self.stdout.write("  Skipped: Already has a blurhash")
            return "skipped"

        if dry_run:
            self.stdout.write(
                f"  [DRY RUN] Would generate blurhash for PostImage {image.id}"
            )
            return "processed"

        image_blurhash = generate_blurhash_for_post_image(image)
        if not image_blurhash:
            self.stdout.write(
                self.style.WARNING(
                    f"  Skipped: Unable to generate blurhash for PostImage {image.id}"
                )
            )
            return "skipped"

        PostImage.objects.filter(pk=image.pk).update(blurhash=image_blurhash)
        self.stdout.write(self.style.SUCCESS("  Generated blurhash"))
        return "processed"

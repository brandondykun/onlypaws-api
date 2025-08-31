"""
Management command to generate embeddings for existing PostImage instances.
"""

from django.core.management.base import BaseCommand
from apps.core_app.models import PostImage
from apps.core_app.services import get_embedding_service


class Command(BaseCommand):
    help = "Generate embeddings for PostImage instances that don't have them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of images to process in each batch (default: 50)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate embeddings even if they already exist",
        )
        parser.add_argument(
            "--post-id", type=int, help="Process images for a specific post ID only"
        )
        parser.add_argument(
            "--image-id", type=int, help="Process a specific PostImage ID only"
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        force = options["force"]
        post_id = options.get("post_id")
        image_id = options.get("image_id")

        # Build queryset
        queryset = PostImage.objects.all()

        if image_id:
            queryset = queryset.filter(id=image_id)
        elif post_id:
            queryset = queryset.filter(post__id=post_id)

        if not force:
            queryset = queryset.filter(embedding__isnull=True)

        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No images need embedding generation.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting embedding generation for {total_count} images..."
            )
        )

        # Get the embedding service
        embedding_service = get_embedding_service()

        processed = 0
        failed = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = queryset[i : i + batch_size]

            for post_image in batch:
                try:
                    self.stdout.write(
                        f"Processing PostImage {post_image.id} {post_image.image.path}..."
                    )

                    success = embedding_service.generate_embedding_for_post_image(
                        post_image
                    )

                    if success:
                        processed += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Generated embedding for PostImage {post_image.id}"
                            )
                        )
                    else:
                        failed += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ Failed to generate embedding for PostImage {post_image.id}"
                            )
                        )

                except Exception as e:
                    failed += 1
                    import traceback

                    error_details = traceback.format_exc()
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Error processing PostImage {post_image.id}: {str(e)}\n{error_details}"
                        )
                    )

            # Progress update
            self.stdout.write(
                self.style.SUCCESS(
                    f"Batch complete. Processed: {processed}, Failed: {failed}, "
                    f"Remaining: {total_count - processed - failed}"
                )
            )

        # Final summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Embedding generation complete!\n"
                f"Total processed: {processed}\n"
                f"Total failed: {failed}\n"
                f"Total images: {total_count}"
            )
        )

        if failed > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{failed} images failed processing. Check logs for details."
                )
            )

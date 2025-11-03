"""
Management command to generate embeddings for existing PostImage instances.
"""

from django.core.management.base import BaseCommand
from apps.posts_app.models import PostImage
from apps.core_app.services import get_embedding_service
from apps.core_app.tasks import batch_generate_embeddings_task


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
        parser.add_argument(
            "--async",
            action="store_true",
            help="Use Celery to process embeddings asynchronously (recommended for large batches)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Process embeddings synchronously (useful for development/debugging)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        force = options["force"]
        post_id = options.get("post_id")
        image_id = options.get("image_id")
        use_async = options.get("async")
        use_sync = options.get("sync")

        # Default to async if neither is specified
        if not use_async and not use_sync:
            use_async = True

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
                f"Starting embedding generation for {total_count} images using "
                f"{'async' if use_async else 'sync'} processing..."
            )
        )

        # Handle async processing
        if use_async:
            self._handle_async_processing(queryset, batch_size, force, total_count)
            return

        # Handle sync processing (original logic)
        self._handle_sync_processing(queryset, batch_size, total_count)

    def _handle_async_processing(self, queryset, batch_size, force, total_count):
        """Handle asynchronous processing using Celery tasks."""
        try:
            # Get list of IDs to process
            post_image_ids = list(queryset.values_list("id", flat=True))

            if not post_image_ids:
                self.stdout.write(self.style.SUCCESS("No images found to process."))
                return

            # Queue the batch processing task
            task_result = batch_generate_embeddings_task.delay(
                post_image_ids, batch_size
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Queued batch processing task: {task_result.id}\n"
                    f"Total images: {len(post_image_ids)}\n"
                    f"Batch size: {batch_size}\n"
                    f"Estimated batches: {(len(post_image_ids) + batch_size - 1) // batch_size}"
                )
            )

            self.stdout.write(
                self.style.WARNING(
                    "\nNote: Processing is happening in the background.\n"
                    "Use Celery monitoring tools or check logs to track progress.\n"
                    "Individual embedding tasks will be queued and processed by workers."
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to queue async processing: {str(e)}\n"
                    "Make sure Redis and Celery workers are running."
                )
            )

    def _handle_sync_processing(self, queryset, batch_size, total_count):
        """Handle synchronous processing (original logic)."""
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

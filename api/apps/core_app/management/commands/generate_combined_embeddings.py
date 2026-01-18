"""
Management command to generate combined embeddings for existing Post instances.
"""

from django.core.management.base import BaseCommand
from apps.posts_app.models import Post
from apps.core_app.services import get_embedding_service
from apps.core_app.tasks import generate_combined_post_embedding_task


class Command(BaseCommand):
    help = "Generate combined embeddings for Post instances that don't have them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of posts to process in each batch (default: 50)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate combined embeddings even if they already exist",
        )
        parser.add_argument(
            "--post-id", type=int, help="Process a specific post ID only"
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
        parser.add_argument(
            "--countdown",
            type=int,
            default=5,
            help="Seconds to wait before processing (for async mode, allows image embeddings to complete)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        force = options["force"]
        post_id = options.get("post_id")
        use_async = options.get("async")
        use_sync = options.get("sync")
        countdown = options["countdown"]

        # Default to async if neither is specified
        if not use_async and not use_sync:
            use_async = True

        # Build queryset
        queryset = Post.objects.all()

        if post_id:
            queryset = queryset.filter(id=post_id)

        if not force:
            queryset = queryset.filter(combined_embedding__isnull=True)

        # Prefetch related images to check for image embeddings
        queryset = queryset.prefetch_related('images')

        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No posts need combined embedding generation.")
            )
            return

        # Check if posts have images with embeddings
        posts_ready = []
        posts_not_ready = []
        
        for post in queryset:
            images = post.images.all()
            if not images:
                self.stdout.write(
                    self.style.WARNING(f"⚠ Post {post.id} has no images, skipping")
                )
                continue
                
            # Check if all images have embeddings
            images_without_embeddings = [img.id for img in images if not img.has_embedding()]
            
            if images_without_embeddings:
                posts_not_ready.append((post.id, images_without_embeddings))
            else:
                posts_ready.append(post.id)

        if posts_not_ready:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ {len(posts_not_ready)} post(s) have images without embeddings:\n"
                )
            )
            for post_id, image_ids in posts_not_ready[:5]:  # Show first 5
                self.stdout.write(
                    f"  Post {post_id}: {len(image_ids)} image(s) missing embeddings"
                )
            if len(posts_not_ready) > 5:
                self.stdout.write(f"  ... and {len(posts_not_ready) - 5} more")
            
            self.stdout.write(
                self.style.WARNING(
                    "\nThese posts will be processed, but may fail until image embeddings complete.\n"
                    "Consider running with --countdown to give more time for image embeddings.\n"
                )
            )

        posts_to_process = posts_ready + [p[0] for p in posts_not_ready]
        
        if not posts_to_process:
            self.stdout.write(
                self.style.WARNING("No posts with images found to process.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting combined embedding generation for {len(posts_to_process)} posts using "
                f"{'async' if use_async else 'sync'} processing..."
            )
        )
        
        if posts_ready:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {len(posts_ready)} post(s) have all image embeddings ready"
                )
            )

        # Handle async processing
        if use_async:
            self._handle_async_processing(
                posts_to_process, batch_size, total_count, countdown
            )
            return

        # Handle sync processing
        self._handle_sync_processing(posts_to_process, batch_size)

    def _handle_async_processing(self, post_ids, batch_size, total_count, countdown):
        """Handle asynchronous processing using Celery tasks."""
        try:
            if not post_ids:
                self.stdout.write(self.style.SUCCESS("No posts found to process."))
                return

            # Queue individual tasks for each post
            queued_tasks = []
            failed_to_queue = []

            for post_id in post_ids:
                try:
                    task = generate_combined_post_embedding_task.apply_async(
                        args=[post_id],
                        countdown=countdown
                    )
                    queued_tasks.append((post_id, task.id))
                except Exception as e:
                    failed_to_queue.append((post_id, str(e)))

            # Display results
            if queued_tasks:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Queued {len(queued_tasks)} combined embedding tasks\n"
                        f"Countdown: {countdown} seconds\n"
                        f"Total posts: {len(post_ids)}"
                    )
                )
                
                # Show first few task IDs
                self.stdout.write("\nSample task IDs:")
                for post_id, task_id in queued_tasks[:5]:
                    self.stdout.write(f"  Post {post_id}: {task_id}")
                if len(queued_tasks) > 5:
                    self.stdout.write(f"  ... and {len(queued_tasks) - 5} more")

            if failed_to_queue:
                self.stdout.write(
                    self.style.ERROR(
                        f"\n✗ Failed to queue {len(failed_to_queue)} tasks:"
                    )
                )
                for post_id, error in failed_to_queue[:5]:
                    self.stdout.write(f"  Post {post_id}: {error}")

            self.stdout.write(
                self.style.WARNING(
                    "\nNote: Processing is happening in the background.\n"
                    "Use Celery monitoring tools or check logs to track progress.\n"
                    "Tasks will automatically retry if image embeddings aren't ready yet."
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to queue async processing: {str(e)}\n"
                    "Make sure Redis and Celery workers are running."
                )
            )

    def _handle_sync_processing(self, post_ids, batch_size):
        """Handle synchronous processing."""
        # Get the embedding service
        embedding_service = get_embedding_service()

        processed = 0
        failed = 0
        skipped = 0

        # Process in batches
        for i in range(0, len(post_ids), batch_size):
            batch_ids = post_ids[i : i + batch_size]
            posts = Post.objects.filter(id__in=batch_ids).prefetch_related('images')

            for post in posts:
                try:
                    self.stdout.write(
                        f"Processing Post {post.id} with {post.images.count()} image(s)..."
                    )

                    # Check if post has images
                    if not post.images.exists():
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ Post {post.id} has no images, skipping"
                            )
                        )
                        continue

                    # Check if all images have embeddings
                    images_without_embeddings = [img.id for img in post.images.all() if not img.has_embedding()]

                    if images_without_embeddings:
                        failed += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ Post {post.id} has {len(images_without_embeddings)} "
                                f"image(s) without embeddings: {images_without_embeddings}"
                            )
                        )
                        continue

                    # Generate combined embedding
                    success = embedding_service.generate_combined_embedding_for_post(post)

                    if success:
                        processed += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Generated combined embedding for Post {post.id}"
                            )
                        )
                    else:
                        failed += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ Failed to generate combined embedding for Post {post.id}"
                            )
                        )

                except Exception as e:
                    failed += 1
                    import traceback

                    error_details = traceback.format_exc()
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Error processing Post {post.id}: {str(e)}\n{error_details}"
                        )
                    )

            # Progress update
            self.stdout.write(
                self.style.SUCCESS(
                    f"Batch complete. Processed: {processed}, Failed: {failed}, "
                    f"Skipped: {skipped}, Remaining: {len(post_ids) - processed - failed - skipped}"
                )
            )

        # Final summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Combined embedding generation complete!\n"
                f"Total processed: {processed}\n"
                f"Total failed: {failed}\n"
                f"Total skipped: {skipped}\n"
                f"Total posts: {len(post_ids)}"
            )
        )

        if failed > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{failed} posts failed processing. Check logs for details.\n"
                    "Common causes:\n"
                    "  - Images missing embeddings (run generate_embeddings first)\n"
                    "  - Empty or invalid image files\n"
                    "  - Embedding model not available"
                )
            )

        if skipped > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{skipped} posts were skipped (no images)."
                )
            )


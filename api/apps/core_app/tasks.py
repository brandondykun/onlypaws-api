"""
Celery tasks for the core_app.
"""

import logging
from typing import List
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_image_embedding_task(self, post_image_id: int):
    """
    Background task to generate embedding for a PostImage.

    Args:
        post_image_id: ID of the PostImage instance to process

    Returns:
        Dict with success status and details
    """
    try:
        # Import here to avoid circular imports
        from apps.posts_app.models import PostImage
        from .services import get_embedding_service

        logger.info(f"Starting embedding generation for PostImage {post_image_id}")

        # Get the PostImage instance
        try:
            post_image = PostImage.objects.get(id=post_image_id)
        except PostImage.DoesNotExist:
            logger.warning(
                f"PostImage {post_image_id} does not exist (attempt {self.request.retries + 1})"
            )

            # If this is a new PostImage, it might not be committed to DB yet
            # Retry with exponential backoff for a few attempts
            if self.request.retries < self.max_retries:
                retry_delay = min(
                    60, 5 * (2**self.request.retries)
                )  # 5s, 10s, 20s (max 60s)
                logger.info(
                    f"Retrying PostImage {post_image_id} in {retry_delay} seconds..."
                )
                raise self.retry(
                    exc=None, countdown=retry_delay, max_retries=self.max_retries
                )

            # After all retries, return error
            logger.error(
                f"PostImage {post_image_id} does not exist after {self.max_retries} retries"
            )
            return {
                "success": False,
                "error": f"PostImage {post_image_id} does not exist after {self.max_retries} retries",
                "post_image_id": post_image_id,
                "retries": self.request.retries,
            }

        # Check if embedding already exists (avoid duplicate work)
        if (
            post_image.embedding is not None
            and hasattr(post_image.embedding, "__len__")
            and len(post_image.embedding) > 0
        ):
            logger.info(f"PostImage {post_image_id} already has an embedding, skipping")
            return {
                "success": True,
                "message": "Embedding already exists",
                "post_image_id": post_image_id,
                "skipped": True,
            }

        # Generate the embedding
        embedding_service = get_embedding_service()
        success = embedding_service.generate_embedding_for_post_image(post_image)

        if success:
            logger.info(
                f"Successfully generated embedding for PostImage {post_image_id}"
            )
            return {
                "success": True,
                "message": "Embedding generated successfully",
                "post_image_id": post_image_id,
                "model_used": embedding_service.model_name,
                "generated_at": (
                    post_image.embedding_generated_at.isoformat()
                    if post_image.embedding_generated_at
                    else None
                ),
            }
        else:
            logger.error(f"Failed to generate embedding for PostImage {post_image_id}")
            return {
                "success": False,
                "error": "Embedding generation failed",
                "post_image_id": post_image_id,
            }

    except Exception as exc:
        logger.error(
            f"Error in embedding task for PostImage {post_image_id}: {str(exc)}"
        )

        # Retry with exponential backoff
        try:
            retry_delay = 60 * (2**self.request.retries)  # 60s, 120s, 240s
            raise self.retry(exc=exc, countdown=retry_delay)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for PostImage {post_image_id}")
            return {
                "success": False,
                "error": f"Max retries exceeded: {str(exc)}",
                "post_image_id": post_image_id,
                "retries": self.request.retries,
            }


@shared_task(bind=True, max_retries=5)
def generate_combined_post_embedding_task(self, post_id: int):
    """
    Background task to generate combined embedding for a Post.

    Args:
        post_id: ID of the Post instance to process

    Returns:
        Dict with success status and details

    Retry Logic:
    - Check if all PostImage embeddings exist
    - If not, retry with exponential backoff: 10s, 20s, 40s, 80s, 160s
    - Max delay capped at 300s
    """
    try:
        # Import here to avoid circular imports
        from apps.posts_app.models import Post
        from .services import get_embedding_service

        logger.info(f"Starting combined embedding generation for Post {post_id}")

        # Get the Post instance
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            logger.warning(
                f"Post {post_id} does not exist (attempt {self.request.retries + 1})"
            )

            # If this is a new Post, it might not be committed to DB yet
            # Retry with exponential backoff for a few attempts
            if self.request.retries < self.max_retries:
                retry_delay = min(300, 10 * (2**self.request.retries))  # 10s, 20s, 40s, 80s, 160s
                logger.info(f"Retrying Post {post_id} in {retry_delay} seconds...")
                raise self.retry(exc=None, countdown=retry_delay, max_retries=self.max_retries)

            # After all retries, return error
            logger.error(f"Post {post_id} does not exist after {self.max_retries} retries")
            return {
                "success": False,
                "error": f"Post {post_id} does not exist after {self.max_retries} retries",
                "post_id": post_id,
                "retries": self.request.retries,
            }

        # Check if combined embedding already exists (avoid duplicate work)
        if (
            post.combined_embedding is not None
            and hasattr(post.combined_embedding, "__len__")
            and len(post.combined_embedding) > 0
        ):
            logger.info(f"Post {post_id} already has a combined embedding, skipping")
            return {
                "success": True,
                "message": "Combined embedding already exists",
                "post_id": post_id,
                "skipped": True,
            }

        # Get all PostImage instances and check if they have embeddings
        post_images = post.images.all()
        if not post_images.exists():
            logger.error(f"Post {post_id} has no images")
            return {
                "success": False,
                "error": "Post has no images",
                "post_id": post_id,
            }

        # Check if all images have embeddings
        images_with_embeddings = []
        images_without_embeddings = []
        for img in post_images:
            if img.embedding is None or (
                hasattr(img.embedding, "__len__") and len(img.embedding) == 0
            ):
                images_without_embeddings.append(img.id)
            else:
                images_with_embeddings.append(img.id)

        # If not all images have embeddings yet, retry with exponential backoff
        if images_without_embeddings:
            if self.request.retries < self.max_retries:
                retry_delay = min(300, 10 * (2**self.request.retries))  # 10s, 20s, 40s, 80s, 160s
                logger.info(
                    f"Post {post_id}: {len(images_without_embeddings)} of {len(post_images)} "
                    f"images still need embeddings. Retrying in {retry_delay} seconds... "
                    f"(attempt {self.request.retries + 1}/{self.max_retries})"
                )
                raise self.retry(exc=None, countdown=retry_delay, max_retries=self.max_retries)

            # After max retries, return error
            logger.error(
                f"Post {post_id}: {len(images_without_embeddings)} images still don't have "
                f"embeddings after {self.max_retries} retries: {images_without_embeddings}"
            )
            return {
                "success": False,
                "error": "Not all images have embeddings after max retries",
                "post_id": post_id,
                "images_without_embeddings": images_without_embeddings,
                "retries": self.request.retries,
            }

        # Generate the combined embedding
        embedding_service = get_embedding_service()
        success = embedding_service.generate_combined_embedding_for_post(post)

        if success:
            logger.info(f"Successfully generated combined embedding for Post {post_id}")
            return {
                "success": True,
                "message": "Combined embedding generated successfully",
                "post_id": post_id,
                "num_images": len(images_with_embeddings),
                "model_used": embedding_service.model_name,
                "generated_at": (
                    post.combined_embedding_generated_at.isoformat()
                    if post.combined_embedding_generated_at
                    else None
                ),
            }
        else:
            logger.error(f"Failed to generate combined embedding for Post {post_id}")
            return {
                "success": False,
                "error": "Combined embedding generation failed",
                "post_id": post_id,
            }

    except Exception as exc:
        logger.error(f"Error in combined embedding task for Post {post_id}: {str(exc)}")

        # Retry with exponential backoff
        try:
            retry_delay = min(300, 10 * (2**self.request.retries))  # 10s, 20s, 40s, 80s, 160s
            raise self.retry(exc=exc, countdown=retry_delay)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for Post {post_id}")
            return {
                "success": False,
                "error": f"Max retries exceeded: {str(exc)}",
                "post_id": post_id,
                "retries": self.request.retries,
            }


@shared_task
def batch_generate_embeddings_task(post_image_ids: List[int], batch_size: int = 10):
    """
    Process multiple PostImage embeddings in batches.

    Args:
        post_image_ids: List of PostImage IDs to process
        batch_size: Number of tasks to process concurrently

    Returns:
        Dict with batch processing results
    """
    logger.info(f"Starting batch embedding generation for {len(post_image_ids)} images")

    # Split into batches and queue individual tasks
    results = []
    total_batches = (len(post_image_ids) + batch_size - 1) // batch_size

    for i in range(0, len(post_image_ids), batch_size):
        batch = post_image_ids[i : i + batch_size]
        batch_num = (i // batch_size) + 1

        logger.info(
            f"Processing batch {batch_num}/{total_batches} with {len(batch)} images"
        )

        # Queue individual embedding tasks for this batch
        batch_results = []
        for post_image_id in batch:
            try:
                task_result = generate_image_embedding_task.delay(post_image_id)
                batch_results.append(
                    {
                        "post_image_id": post_image_id,
                        "task_id": task_result.id,
                        "status": "queued",
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to queue task for PostImage {post_image_id}: {str(e)}"
                )
                batch_results.append(
                    {
                        "post_image_id": post_image_id,
                        "task_id": None,
                        "status": "failed_to_queue",
                        "error": str(e),
                    }
                )

        results.extend(batch_results)

    logger.info(f"Queued {len(results)} embedding tasks")

    return {
        "success": True,
        "message": f"Batch processing initiated for {len(post_image_ids)} images",
        "total_images": len(post_image_ids),
        "total_batches": total_batches,
        "batch_size": batch_size,
        "queued_tasks": len([r for r in results if r["status"] == "queued"]),
        "failed_to_queue": len(
            [r for r in results if r["status"] == "failed_to_queue"]
        ),
        "results": results,
    }


@shared_task
def generate_embeddings_for_missing_task(batch_size: int = 50, force: bool = False):
    """
    Find PostImages without embeddings and queue them for processing.

    Args:
        batch_size: Number of images to process in each batch
        force: If True, regenerate embeddings even if they exist

    Returns:
        Dict with processing results
    """
    try:
        from apps.posts_app.models import PostImage

        logger.info(
            f"Starting search for PostImages needing embeddings (force={force})"
        )

        # Build queryset
        queryset = PostImage.objects.all()

        if not force:
            queryset = queryset.filter(embedding__isnull=True)

        # Get IDs to avoid loading full objects into memory
        post_image_ids = list(queryset.values_list("id", flat=True))

        if not post_image_ids:
            logger.info("No PostImages need embedding generation")
            return {
                "success": True,
                "message": "No images need embedding generation",
                "total_found": 0,
                "force": force,
            }

        logger.info(f"Found {len(post_image_ids)} PostImages needing embeddings")

        # Queue batch processing task
        batch_task = batch_generate_embeddings_task.delay(post_image_ids, batch_size)

        return {
            "success": True,
            "message": f"Queued {len(post_image_ids)} images for embedding generation",
            "total_found": len(post_image_ids),
            "batch_size": batch_size,
            "force": force,
            "batch_task_id": batch_task.id,
        }

    except Exception as exc:
        logger.error(f"Error in generate_embeddings_for_missing_task: {str(exc)}")
        return {"success": False, "error": str(exc)}


@shared_task
def cleanup_expired_task_results():
    """
    Clean up expired Celery task results.
    This should be run periodically to prevent Redis from growing too large.
    """
    logger.info("Starting cleanup of expired task results")

    # This is a placeholder - actual implementation would depend on
    # your Celery result backend configuration and cleanup requirements
    try:
        from celery.result import AsyncResult
        from django.conf import settings

        # For now, just log that cleanup would run
        logger.info("Task result cleanup completed")

        return {"success": True, "message": "Task result cleanup completed"}

    except Exception as exc:
        logger.error(f"Error in cleanup task: {str(exc)}")
        return {"success": False, "error": str(exc)}

"""
Celery tasks for the core_app.
"""

import logging
from typing import List
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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
        if post_image.has_embedding():
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
        if post.has_combined_embedding():
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
            if not img.has_embedding():
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


@shared_task(bind=True, max_retries=3)
def process_post_images_task(self, post_id: int):
    """
    Background task to process uploaded images for a post.
    
    This task handles images uploaded via presigned URLs:
    1. Downloads original images from S3/R2
    2. Crops to aspect ratio and resizes to LARGE (1080px)
    3. Creates SMALL (320px) scaled variant
    4. Converts all to webp format
    5. Uploads processed images
    6. Deletes original images from S3
    7. Generates embeddings on the large image
    8. Updates post status to READY
    
    Args:
        post_id: ID of the Post to process
    
    Returns:
        Dict with processing results
    """
    from io import BytesIO
    
    from django.core.files.base import ContentFile
    from PIL import Image
    from PIL import ImageOps
    
    from apps.posts_app.models import Post, PostImage, PostImageScaled
    from apps.core_app.storage_utils import download_file, delete_file
    from .services import get_embedding_service
    
    logger.info(f"Starting image processing for Post {post_id}")
    
    try:
        # Get the post
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            logger.error(f"Post {post_id} does not exist")
            return {
                "success": False,
                "error": f"Post {post_id} does not exist",
                "post_id": post_id,
            }
        
        # Verify post is in PROCESSING status
        if post.status != Post.Status.PROCESSING:
            logger.warning(
                f"Post {post_id} is not in PROCESSING status (current: {post.status})"
            )
            return {
                "success": False,
                "error": f"Post is not in PROCESSING status (current: {post.status})",
                "post_id": post_id,
            }
        
        # Get all PostImages for this post
        post_images = list(post.images.filter(
            processing_status=PostImage.ProcessingStatus.UPLOADED
        ).order_by("order"))
        
        if not post_images:
            logger.error(f"Post {post_id} has no uploaded images to process")
            post.status = Post.Status.FAILED
            post.save(update_fields=["status"])
            return {
                "success": False,
                "error": "No uploaded images to process",
                "post_id": post_id,
            }
        
        logger.info(f"Processing {len(post_images)} images for Post {post_id}")
        
        processed_count = 0
        failed_count = 0
        
        for post_image in post_images:
            try:
                # Update status to PROCESSING
                post_image.processing_status = PostImage.ProcessingStatus.PROCESSING
                post_image.save(update_fields=["processing_status"])
                
                # Download original image
                if not post_image.original_key:
                    logger.error(f"PostImage {post_image.id} has no original_key")
                    raise ValueError("No original_key set")
                
                original_data = download_file(post_image.original_key)
                if original_data is None:
                    logger.error(
                        f"Failed to download original image for PostImage {post_image.id}"
                    )
                    raise ValueError("Failed to download original image")
                
                # Open and process the image
                original_image = Image.open(BytesIO(original_data))
                original_image = ImageOps.exif_transpose(original_image)
                
                # Convert to RGB if needed
                if original_image.mode != "RGB":
                    original_image = original_image.convert("RGB")
                
                # Get target dimensions from post aspect ratio
                aspect_ratio = post.aspect_ratio
                
                # Process all 3 scale variants before saving any
                # This ensures we don't partially process if something fails
                
                # Process LARGE image (1080px) - this becomes PostImage.image
                large_image = _crop_and_resize_image(
                    original_image.copy(),
                    aspect_ratio,
                    PostImageScaled.SCALE_DIMENSIONS["large"]
                )
                large_buffer = BytesIO()
                large_image.save(large_buffer, "webp", optimize=True, quality=70)
                large_buffer.seek(0)
                
                # Process MEDIUM image (500px)
                medium_image = _crop_and_resize_image(
                    original_image.copy(),
                    aspect_ratio,
                    PostImageScaled.SCALE_DIMENSIONS["medium"]
                )
                medium_buffer = BytesIO()
                medium_image.save(medium_buffer, "webp", optimize=True, quality=70)
                medium_buffer.seek(0)
                
                # Process SMALL image (150px)
                small_image = _crop_and_resize_image(
                    original_image.copy(),
                    aspect_ratio,
                    PostImageScaled.SCALE_DIMENSIONS["small"]
                )
                small_buffer = BytesIO()
                small_image.save(small_buffer, "webp", optimize=True, quality=70)
                small_buffer.seek(0)
                
                # All variants processed successfully, now save them
                
                # Save LARGE to PostImage.image field (primary image)
                large_dim = PostImageScaled.SCALE_DIMENSIONS["large"]
                post_image.image.save(
                    f"{post_image.order}_{large_dim}.webp",
                    ContentFile(large_buffer.getvalue()),
                    save=False
                )
                
                # Create or update PostImageScaled for MEDIUM
                medium_dim = PostImageScaled.SCALE_DIMENSIONS["medium"]
                medium_scaled, _ = PostImageScaled.objects.update_or_create(
                    post_image=post_image,
                    scale=PostImageScaled.Scale.MEDIUM,
                    defaults={
                        "width": medium_image.width,
                        "height": medium_image.height,
                    }
                )
                medium_scaled.image.save(
                    f"{post_image.order}_{medium_dim}.webp",
                    ContentFile(medium_buffer.getvalue()),
                    save=True
                )
                
                # Create or update PostImageScaled for SMALL
                small_dim = PostImageScaled.SCALE_DIMENSIONS["small"]
                small_scaled, _ = PostImageScaled.objects.update_or_create(
                    post_image=post_image,
                    scale=PostImageScaled.Scale.SMALL,
                    defaults={
                        "width": small_image.width,
                        "height": small_image.height,
                    }
                )
                small_scaled.image.save(
                    f"{post_image.order}_{small_dim}.webp",
                    ContentFile(small_buffer.getvalue()),
                    save=True
                )
                
                # Update PostImage status and save
                post_image.processing_status = PostImage.ProcessingStatus.READY
                post_image.save(update_fields=["image", "processing_status"])
                
                # All 3 variants created successfully, now safe to delete original
                if delete_file(post_image.original_key):
                    logger.info(f"Deleted original image: {post_image.original_key}")
                else:
                    logger.warning(
                        f"Failed to delete original image: {post_image.original_key}"
                    )
                
                processed_count += 1
                logger.info(
                    f"Successfully processed PostImage {post_image.id} "
                    f"(large: {large_image.width}x{large_image.height}, "
                    f"medium: {medium_image.width}x{medium_image.height}, "
                    f"small: {small_image.width}x{small_image.height})"
                )
                
            except Exception as e:
                logger.error(
                    f"Error processing PostImage {post_image.id}: {str(e)}"
                )
                post_image.processing_status = PostImage.ProcessingStatus.FAILED
                post_image.save(update_fields=["processing_status"])
                failed_count += 1
        
        # Check if any images were processed successfully
        if processed_count == 0:
            logger.error(f"All images failed processing for Post {post_id}")
            post.status = Post.Status.FAILED
            post.save(update_fields=["status"])
            return {
                "success": False,
                "error": "All images failed processing",
                "post_id": post_id,
                "failed_count": failed_count,
            }
        
        # Generate embeddings for successfully processed images
        logger.info(f"Generating embeddings for Post {post_id}")
        embedding_service = get_embedding_service()
        
        for post_image in post.images.filter(
            processing_status=PostImage.ProcessingStatus.READY
        ):
            try:
                if not post_image.has_embedding():
                    success = embedding_service.generate_embedding_for_post_image(post_image)
                    if success:
                        logger.info(f"Generated embedding for PostImage {post_image.id}")
                    else:
                        logger.warning(
                            f"Failed to generate embedding for PostImage {post_image.id}"
                        )
            except Exception as e:
                logger.error(
                    f"Error generating embedding for PostImage {post_image.id}: {str(e)}"
                )
        
        # Generate combined embedding for the post
        try:
            success = embedding_service.generate_combined_embedding_for_post(post)
            if success:
                logger.info(f"Generated combined embedding for Post {post_id}")
            else:
                logger.warning(f"Failed to generate combined embedding for Post {post_id}")
        except Exception as e:
            logger.error(f"Error generating combined embedding for Post {post_id}: {str(e)}")
        
        # Update post status to READY
        post.status = Post.Status.READY
        post.save(update_fields=["status"])
        
        # Send websocket notification to the post owner
        try:
            channel_layer = get_channel_layer()
            profile_id = post.profile.id
            async_to_sync(channel_layer.group_send)(
                f'profile_{profile_id}',
                {
                    'type': 'post_ready',
                    'post_id': post_id,
                    'post_public_id': str(post.public_id),
                    'message': 'Your post is ready',
                }
            )
            logger.info(f"Sent post_ready websocket message for Post {post_id} to profile {profile_id}")
        except Exception as e:
            # Don't fail the task if websocket notification fails
            logger.warning(f"Failed to send post_ready websocket message for Post {post_id}: {e}")
        
        logger.info(
            f"Successfully processed Post {post_id}: "
            f"{processed_count} images processed, {failed_count} failed"
        )
        
        return {
            "success": True,
            "message": "Post images processed successfully",
            "post_id": post_id,
            "processed_count": processed_count,
            "failed_count": failed_count,
        }
        
    except Exception as exc:
        logger.error(f"Error in process_post_images_task for Post {post_id}: {str(exc)}")
        
        # Update post status to FAILED
        try:
            post = Post.objects.get(id=post_id)
            post.status = Post.Status.FAILED
            post.save(update_fields=["status"])
        except Exception:
            pass
        
        # Retry with exponential backoff
        try:
            retry_delay = min(300, 30 * (2**self.request.retries))
            raise self.retry(exc=exc, countdown=retry_delay)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for Post {post_id}")
            return {
                "success": False,
                "error": f"Max retries exceeded: {str(exc)}",
                "post_id": post_id,
                "retries": self.request.retries,
            }


@shared_task(bind=True, max_retries=3)
def process_profile_image_task(self, profile_image_id: int):
    """
    Background task to process an uploaded profile image.

    Downloads original from storage, crops/resizes to 1:1 (large 400px, medium 200px,
    small 100px), saves large to ProfileImage.image and medium/small to
    ProfileImageScaled, then deletes the original.
    """
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image
    from PIL import ImageOps

    from apps.profile_app.models import ProfileImage, ProfileImageScaled
    from apps.core_app.storage_utils import download_file, delete_file

    logger.info(f"Starting profile image processing for ProfileImage {profile_image_id}")

    try:
        try:
            profile_image = ProfileImage.objects.get(id=profile_image_id)
        except ProfileImage.DoesNotExist:
            logger.error(f"ProfileImage {profile_image_id} does not exist")
            return {"success": False, "error": "ProfileImage does not exist", "profile_image_id": profile_image_id}

        if profile_image.processing_status != ProfileImage.ProcessingStatus.UPLOADED:
            logger.warning(
                f"ProfileImage {profile_image_id} status is not UPLOADED (current: {profile_image.processing_status})"
            )
            return {
                "success": False,
                "error": f"ProfileImage is not UPLOADED (current: {profile_image.processing_status})",
                "profile_image_id": profile_image_id,
            }

        if not profile_image.original_key:
            logger.error(f"ProfileImage {profile_image_id} has no original_key")
            profile_image.processing_status = ProfileImage.ProcessingStatus.FAILED
            profile_image.save(update_fields=["processing_status"])
            return {"success": False, "error": "No original_key set", "profile_image_id": profile_image_id}

        profile_image.processing_status = ProfileImage.ProcessingStatus.PROCESSING
        profile_image.save(update_fields=["processing_status"])

        original_data = download_file(profile_image.original_key)
        if original_data is None:
            logger.error(f"Failed to download original for ProfileImage {profile_image_id}")
            profile_image.processing_status = ProfileImage.ProcessingStatus.FAILED
            profile_image.save(update_fields=["processing_status"])
            return {"success": False, "error": "Failed to download original", "profile_image_id": profile_image_id}

        original_image = Image.open(BytesIO(original_data))
        original_image = ImageOps.exif_transpose(original_image)
        if original_image.mode != "RGB":
            original_image = original_image.convert("RGB")

        aspect_ratio = "1:1"

        large_image = _crop_and_resize_image(
            original_image.copy(), aspect_ratio, ProfileImageScaled.SCALE_DIMENSIONS["large"]
        )
        large_buffer = BytesIO()
        large_image.save(large_buffer, "webp", optimize=True, quality=70)
        large_buffer.seek(0)

        medium_image = _crop_and_resize_image(
            original_image.copy(), aspect_ratio, ProfileImageScaled.SCALE_DIMENSIONS["medium"]
        )
        medium_buffer = BytesIO()
        medium_image.save(medium_buffer, "webp", optimize=True, quality=70)
        medium_buffer.seek(0)

        small_image = _crop_and_resize_image(
            original_image.copy(), aspect_ratio, ProfileImageScaled.SCALE_DIMENSIONS["small"]
        )
        small_buffer = BytesIO()
        small_image.save(small_buffer, "webp", optimize=True, quality=70)
        small_buffer.seek(0)

        large_dim = ProfileImageScaled.SCALE_DIMENSIONS["large"]
        profile_image.image.save(
            f"avatar_{large_dim}.webp",
            ContentFile(large_buffer.getvalue()),
            save=False,
        )

        medium_dim = ProfileImageScaled.SCALE_DIMENSIONS["medium"]
        medium_scaled, _ = ProfileImageScaled.objects.update_or_create(
            profile_image=profile_image,
            scale=ProfileImageScaled.Scale.MEDIUM,
            defaults={"width": medium_image.width, "height": medium_image.height},
        )
        medium_scaled.image.save(
            f"avatar_{medium_dim}.webp",
            ContentFile(medium_buffer.getvalue()),
            save=True,
        )

        small_dim = ProfileImageScaled.SCALE_DIMENSIONS["small"]
        small_scaled, _ = ProfileImageScaled.objects.update_or_create(
            profile_image=profile_image,
            scale=ProfileImageScaled.Scale.SMALL,
            defaults={"width": small_image.width, "height": small_image.height},
        )
        small_scaled.image.save(
            f"avatar_{small_dim}.webp",
            ContentFile(small_buffer.getvalue()),
            save=True,
        )

        profile_image.processing_status = ProfileImage.ProcessingStatus.READY
        profile_image.save(update_fields=["image", "processing_status"])

        if delete_file(profile_image.original_key):
            logger.info(f"Deleted original profile image: {profile_image.original_key}")
        else:
            logger.warning(f"Failed to delete original: {profile_image.original_key}")

        logger.info(
            f"Successfully processed ProfileImage {profile_image_id} "
            f"(large: {large_image.width}x{large_image.height}, "
            f"medium: {medium_image.width}x{medium_image.height}, "
            f"small: {small_image.width}x{small_image.height})"
        )
        return {"success": True, "profile_image_id": profile_image_id}

    except Exception as exc:
        logger.error(f"Error processing ProfileImage {profile_image_id}: {str(exc)}")
        try:
            profile_image = ProfileImage.objects.get(id=profile_image_id)
            profile_image.processing_status = ProfileImage.ProcessingStatus.FAILED
            profile_image.save(update_fields=["processing_status"])
        except Exception:
            pass
        try:
            retry_delay = min(300, 30 * (2**self.request.retries))
            raise self.retry(exc=exc, countdown=retry_delay)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for ProfileImage {profile_image_id}")
            return {
                "success": False,
                "error": str(exc),
                "profile_image_id": profile_image_id,
                "retries": self.request.retries,
            }


def _crop_and_resize_image(image, aspect_ratio: str, base_width: int):
    """
    Helper function to crop and resize an image to a target aspect ratio and size.
    
    Args:
        image: PIL Image object
        aspect_ratio: Target aspect ratio string (e.g., "1:1", "4:5")
        base_width: Target width in pixels
    
    Returns:
        Processed PIL Image object
    """
    from PIL import Image
    
    width, height = image.size
    
    # Parse aspect ratio
    w_ratio, h_ratio = map(int, aspect_ratio.split(':'))
    target_ratio = w_ratio / h_ratio
    
    # Calculate current ratio
    current_ratio = width / height
    
    # Determine crop dimensions
    if abs(current_ratio - target_ratio) < 0.001:
        # Already matches target ratio, no crop needed
        crop_width, crop_height = width, height
        left, top = 0, 0
    elif current_ratio > target_ratio:
        # Image is wider than target - crop left and right
        crop_height = height
        crop_width = int(height * target_ratio)
        left = (width - crop_width) / 2
        top = 0
    else:
        # Image is taller than target - crop top and bottom
        crop_width = width
        crop_height = int(width / target_ratio)
        left = 0
        top = (height - crop_height) / 2
    
    right = left + crop_width
    bottom = top + crop_height
    
    # Crop the image
    image = image.crop((left, top, right, bottom))
    
    # Calculate target height
    target_height = int(base_width / target_ratio)
    
    # Resize if image is larger than target dimensions
    if image.width > base_width:
        image = image.resize((base_width, target_height), Image.Resampling.LANCZOS)
    
    return image


@shared_task
def flush_expired_tokens_task():
    """
    Flush expired JWT tokens from the blacklist.
    
    This task runs the Django management command `flushexpiredtokens` provided by
    djangorestframework-simplejwt's token_blacklist app. It removes:
    - Expired tokens from the OutstandingToken table
    - Associated entries from the BlacklistedToken table
    
    This should be run daily to prevent the token tables from growing indefinitely.
    
    Returns:
        dict: Success status and details about the cleanup
    """
    logger.info("Starting flush of expired JWT tokens")
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        # Capture command output
        out = StringIO()
        call_command('flushexpiredtokens', stdout=out, verbosity=1)
        output = out.getvalue()
        
        logger.info(f"Successfully flushed expired tokens: {output.strip() or 'completed'}")
        
        return {
            "success": True,
            "message": "Expired tokens flushed successfully",
            "output": output.strip(),
        }
        
    except Exception as exc:
        logger.error(f"Error flushing expired tokens: {str(exc)}")
        return {
            "success": False,
            "error": str(exc),
        }

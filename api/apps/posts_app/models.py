"""
Posts app models.
"""
import os
import logging
from django.db import models
from django.core.validators import MaxLengthValidator
from apps.core_app.utils import crop_square_and_resize
from pgvector.django import VectorField, CosineDistance

logger = logging.getLogger(__name__)


class Post(models.Model):
    """Post with image and text."""

    caption = models.TextField(validators=[MaxLengthValidator(1000, message="Caption cannot exceed 1000 characters.")])
    profile = models.ForeignKey("user_app.Profile", on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contains_ai = models.BooleanField(blank=True, default=False)

    def __str__(self):
        return f"Post {self.id} - {self.caption}"


def post_image_path(instance, filename):
    """Generate S3 path (key) for saving post image.
    The key is {user_id}/{profile_id}/{post_id}/{filename}.webp
    """
    user_id = instance.post.profile.user.id
    profile_id = instance.post.profile.id
    post_id = instance.post.id
    path = "{0}/{1}/{2}/{3}".format(user_id, profile_id, post_id, filename)
    # build path based on environment
    if os.environ.get("DJANGO_ENV") == "test":
        path = "images/test/" + path
    elif os.environ.get("DJANGO_ENV") == "dev":
        path = "images/dev/" + path
    else:
        path = "images/" + path

    return path


class PostImage(models.Model):
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=post_image_path)
    order = models.IntegerField(default=0, help_text="Display order of the image in the post")

    # Embedding fields for similarity search
    embedding = VectorField(
        dimensions=512,  # 512-dimensional embedding
        null=True,
        blank=True,
        help_text="Vector embedding for similarity search",
    )
    embedding_model = models.CharField(
        max_length=100,
        default="clip-vit-base-patch32",
        help_text="Model used to generate the embedding",
    )
    embedding_generated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the embedding was generated"
    )

    def save(self, *args, **kwargs):
        # Process image
        self.image = crop_square_and_resize(self.image, image_size=1080)

        # Check if we need to generate embedding
        should_generate_embedding = (
            self.pk is None  # New instance
            or "embedding"
            not in kwargs.get("update_fields", [])  # Not updating embedding field
        )

        # Save first to ensure we have a file path
        super().save(*args, **kwargs)

        # Generate embedding asynchronously if needed
        if should_generate_embedding and (
            self.embedding is None
            or (hasattr(self.embedding, "__len__") and len(self.embedding) == 0)
        ):
            try:
                # Import here to avoid circular imports
                from apps.core_app.tasks import generate_image_embedding_task
                from django.db import transaction

                def queue_embedding_task():
                    """Queue the embedding task after transaction commits."""
                    try:
                        task = generate_image_embedding_task.delay(self.id)
                        logger.info(
                            f"Queued embedding generation task {task.id} for PostImage {self.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to queue embedding task for PostImage {self.id}: {str(e)}"
                        )

                # Queue the task only after the transaction commits
                # This ensures the PostImage exists in the database when the worker runs
                transaction.on_commit(queue_embedding_task)

            except Exception as e:
                # Fallback to synchronous generation if Celery is not available
                logger.warning(
                    f"Failed to queue async embedding task for PostImage {self.id}, "
                    f"falling back to synchronous generation: {str(e)}"
                )

                try:
                    from apps.core_app.services import get_embedding_service

                    get_embedding_service().generate_embedding_for_post_image(self)
                except Exception as sync_error:
                    logger.error(
                        f"Synchronous embedding generation also failed for PostImage {self.id}: {str(sync_error)}"
                    )

    def find_similar_images(self, limit: int = 10, min_similarity: float = 0.1):
        """
        Find similar images based on embedding similarity using pgvector.

        Args:
            limit: Maximum number of similar images to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            QuerySet of similar PostImage instances ordered by similarity
        """
        if self.embedding is None or (
            hasattr(self.embedding, "__len__") and len(self.embedding) == 0
        ):
            return PostImage.objects.none()

        # Use pgvector's CosineDistance for similarity search
        # CosineDistance returns values from 0 (identical) to 2 (opposite)
        # So max_distance = 2 * (1 - min_similarity)
        max_distance = 2 * (1 - min_similarity)

        try:
            return (
                PostImage.objects.filter(embedding__isnull=False)
                .exclude(id=self.id)  # Exclude self
                .annotate(distance=CosineDistance("embedding", self.embedding))
                .filter(distance__lte=max_distance)
                .order_by("distance")[:limit]
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in pgvector query: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Fallback to empty queryset
            return PostImage.objects.none()

    def __str__(self):
        return f"Post {self.post.id} - {self.image.name}"

    class Meta:
        ordering = ["order", "id"]


class SavedPost(models.Model):
    profile = models.ForeignKey(
        "user_app.Profile", on_delete=models.CASCADE, related_name="saved_posts"
    )
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("profile", "post"),)


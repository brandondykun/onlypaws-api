"""
Posts app models.
"""
import os
import logging
import ulid
from django.db import models
from django.core.validators import MaxLengthValidator, MinValueValidator, MaxValueValidator
from django_ulid.models import ULIDField
from apps.core_app.utils import crop_to_aspect_ratio_and_resize
from pgvector.django import VectorField, CosineDistance

from apps.core_app.indexes import HnswIndex

logger = logging.getLogger(__name__)


class Post(models.Model):
    """Post with image and text."""

    class AspectRatio(models.TextChoices):
        SQUARE = "1:1", "Square"
        PORTRAIT = "4:5", "Portrait"

    class Status(models.TextChoices):
        PENDING_UPLOAD = "PENDING_UPLOAD", "Pending Upload"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    class Meta:
        indexes = [
            HnswIndex(
                fields=['combined_embedding'],
                name='post_comb_emb_hnsw_idx',
                opclasses=['vector_cosine_ops'],
                m=32,  # Higher m for better recall at scale
                ef_construction=200,  # Higher ef_construction for better index quality
            ),
        ]

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    caption = models.TextField(validators=[MaxLengthValidator(1000, message="Caption cannot exceed 1000 characters.")])
    aspect_ratio = models.CharField(
        max_length=5,
        choices=AspectRatio.choices,
        default=AspectRatio.SQUARE,
        help_text="Aspect ratio for all images in this post"
    )
    profile = models.ForeignKey("profile_app.Profile", on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contains_ai = models.BooleanField(blank=True, default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.READY,  # Backwards compatible with existing posts
        help_text="Post lifecycle status"
    )

    # Combined embedding fields for multimodal similarity search
    combined_embedding = VectorField(
        dimensions=512,
        null=True,
        blank=True,
        help_text="Combined embedding from images and caption",
    )
    combined_embedding_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the combined embedding was generated",
    )
    combined_embedding_model = models.CharField(
        max_length=100,
        default="clip-vit-base-patch32",
        help_text="Model used to generate the combined embedding",
    )

    def __str__(self):
        return f"Post {self.id} - {self.caption}"

    def has_combined_embedding(self) -> bool:
        """
        Check if this post has a valid combined embedding.
        
        Returns:
            bool: True if post has a valid combined embedding, False otherwise
        """
        return not (
            self.combined_embedding is None
            or (
                hasattr(self.combined_embedding, "__len__")
                and len(self.combined_embedding) == 0
            )
        )

    def queue_combined_embedding_generation(self, countdown: int = 10):
        """
        Queue a task to generate the combined embedding for this post.
        
        Args:
            countdown: Seconds to wait before running the task (to allow image embeddings to complete)
        
        Returns:
            Task ID if successful, None otherwise
        """
        try:
            from apps.core_app.tasks import generate_combined_post_embedding_task
            
            task = generate_combined_post_embedding_task.apply_async(
                args=[self.id],
                countdown=countdown
            )
            logger.info(
                f"Queued combined embedding task {task.id} for Post {self.id} "
                f"(countdown: {countdown}s)"
            )
            return task.id
        except Exception as e:
            logger.error(
                f"Failed to queue combined embedding task for Post {self.id}: {str(e)}"
            )
            return None

    def find_similar_posts(self, min_similarity: float = 0.1):
        """
        Find similar posts based on combined embedding similarity using pgvector.

        Args:
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            QuerySet of similar Post instances ordered by similarity
        """
        if not self.has_combined_embedding():
            return Post.objects.none()

        # Use pgvector's CosineDistance for similarity search
        # CosineDistance returns values from 0 (identical) to 2 (opposite)
        # So max_distance = 2 * (1 - min_similarity)
        max_distance = 2 * (1 - min_similarity)

        try:
            return (
                Post.objects.filter(combined_embedding__isnull=False)
                .exclude(id=self.id)  # Exclude self
                .annotate(distance=CosineDistance("combined_embedding", self.combined_embedding))
                .filter(distance__lte=max_distance)
                .order_by("distance")
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in pgvector query for similar posts: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Fallback to empty queryset
            return Post.objects.none()

    def can_profile_interact(self, profile) -> bool:
        """
        Check if a profile can interact with this post (like, comment, etc.).

        Returns True if:
        - No block exists between the profiles, AND
        - The post's profile is public, OR
        - The profile owns the post, OR
        - The profile follows the post's profile

        Args:
            profile: The Profile instance attempting to interact

        Returns:
            bool: True if the profile can interact, False otherwise
        """
        # Import here to avoid circular imports
        from apps.interactions_app.models import Follow
        from apps.moderation_app.block_utils import are_profiles_blocking

        # Block check
        if are_profiles_blocking(self.profile, profile):
            return False
        # Public profiles allow all interactions
        if not self.profile.is_private:
            return True
        # Can always interact with own posts
        if profile.id == self.profile.id:
            return True
        # For private profiles, must be following
        return Follow.objects.filter(followed=self.profile, followed_by=profile).exists()


def _post_env_prefix():
    """Return the environment prefix for post storage keys."""
    env = os.environ.get("DJANGO_ENV")
    if env == "test":
        return "images/test/"
    if env == "dev":
        return "images/dev/"
    if env == "e2e":
        return "images/e2e/"
    return "images/"


def post_image_path(instance, filename):
    """Generate S3 path (key) for saving post image.
    Key: {env_prefix}posts/<post.public_id>/<order>_1080.webp
    """
    prefix = _post_env_prefix()
    public_id = str(instance.post.public_id)
    return f"{prefix}posts/{public_id}/{instance.order}_1080.webp"


class PostImage(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING_UPLOAD = "PENDING_UPLOAD", "Pending Upload"
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=post_image_path, blank=True, null=True)
    order = models.IntegerField(default=0, help_text="Display order of the image in the post")
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.READY,  # Backwards compatible with existing images
        help_text="Image processing status"
    )
    original_key = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="S3 key for the original uploaded image (before processing)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

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
        # Skip image processing and embedding generation for placeholder images
        # (images with PENDING_UPLOAD status that don't have a file yet)
        is_placeholder = self.processing_status == self.ProcessingStatus.PENDING_UPLOAD
        has_image = bool(self.image)

        # Only process image if:
        # 1. Not a placeholder AND has an image file AND
        # 2. (This is a new instance (self.pk is None), OR
        # 3. update_fields is not specified (full save), OR
        # 4. update_fields includes 'image')
        update_fields = kwargs.get("update_fields", None)
        should_process_image = (
            not is_placeholder
            and has_image
            and (
                self.pk is None  # New instance
                or update_fields is None  # Full save without update_fields
                or (update_fields is not None and "image" in update_fields)  # Explicitly updating image
            )
        )
        
        if should_process_image:
            # Get aspect ratio from parent post, default to SQUARE
            aspect_ratio = getattr(self.post, 'aspect_ratio', Post.AspectRatio.SQUARE) if self.post_id else Post.AspectRatio.SQUARE
            # Process image with the appropriate aspect ratio
            self.image = crop_to_aspect_ratio_and_resize(self.image, aspect_ratio=aspect_ratio)

        # Check if we need to generate embedding
        # Don't generate for placeholders or images without files
        should_generate_embedding = (
            not is_placeholder
            and has_image
            and (
                self.pk is None  # New instance
                or "embedding" not in kwargs.get("update_fields", [])  # Not updating embedding field
            )
        )

        # Save first to ensure we have a file path
        super().save(*args, **kwargs)

        # Generate embedding asynchronously if needed
        if should_generate_embedding and not self.has_embedding():
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

    def has_embedding(self) -> bool:
        """
        Check if this post image has a valid embedding.
        
        Returns:
            bool: True if image has a valid embedding, False otherwise
        """
        return not (
            self.embedding is None
            or (
                hasattr(self.embedding, "__len__")
                and len(self.embedding) == 0
            )
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
        if not self.has_embedding():
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
        indexes = [
            HnswIndex(
                fields=['embedding'],
                name='postimg_emb_hnsw_idx',
                opclasses=['vector_cosine_ops'],
                m=32,
                ef_construction=200,
            ),
        ]


class SavedPost(models.Model):
    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    profile = models.ForeignKey(
        "profile_app.Profile", on_delete=models.CASCADE, related_name="saved_posts"
    )
    post = models.ForeignKey("posts_app.Post", on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("profile", "post"),)


class PostImageTag(models.Model):
    """Represents a profile tagged in a specific post image at a specific location."""

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    post_image = models.ForeignKey(
        "PostImage",
        on_delete=models.CASCADE,
        related_name="tags"
    )
    tagged_profile = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="tagged_in_images"
    )
    tagged_by_profile = models.ForeignKey(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="image_tags_created",
        help_text="The profile that created this tag"
    )

    # Position as percentages (0-100) for responsive positioning
    x_position = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="X coordinate as percentage (0-100) of image width"
    )
    y_position = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Y coordinate as percentage (0-100) of image height"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate tags of the same profile in the same image
        unique_together = [["post_image", "tagged_profile"]]
        indexes = [
            models.Index(fields=["post_image"]),
            models.Index(fields=["tagged_profile"]),
        ]

    def __str__(self):
        return f"{self.tagged_profile.username} tagged in image {self.post_image.id}"


def post_image_scaled_path(instance, filename):
    """Generate S3 path for scaled post images.
    Key: {env_prefix}posts/<post.public_id>/<order>_<scale_dimension>.webp
    """
    prefix = _post_env_prefix()
    public_id = str(instance.post_image.post.public_id)
    dim = PostImageScaled.SCALE_DIMENSIONS[instance.scale]
    return f"{prefix}posts/{public_id}/{instance.post_image.order}_{dim}.webp"


class PostImageScaled(models.Model):
    """
    Stores scaled variants of PostImage for different display contexts.
    
    Note: The LARGE (1080px) image is stored in PostImage.image directly,
    not in PostImageScaled. This model only stores smaller variants.
    """

    class Scale(models.TextChoices):
        SMALL = "small", "Small"              # 150px
        MEDIUM = "medium", "Medium"           # 500px

    # Dimensions for each scale (base width, height calculated from aspect ratio)
    # LARGE (1080px) is stored in PostImage.image, not here
    SCALE_DIMENSIONS = {
        "small": 150,
        "medium": 500,
        "large": 1080,  # Used for PostImage.image processing
    }

    public_id = ULIDField(editable=False, unique=True, default=ulid.new)
    post_image = models.ForeignKey(
        "PostImage",
        on_delete=models.CASCADE,
        related_name="scaled_images"
    )
    scale = models.CharField(max_length=20, choices=Scale.choices)
    image = models.ImageField(upload_to=post_image_scaled_path)
    width = models.PositiveIntegerField(help_text="Width in pixels")
    height = models.PositiveIntegerField(help_text="Height in pixels")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["post_image", "scale"]]
        indexes = [
            models.Index(fields=["post_image", "scale"]),
        ]

    def __str__(self):
        return f"PostImage {self.post_image.id} - {self.scale}"


"""
Services for handling image embeddings and similarity search.
"""

import logging
import os
from typing import List, Optional
from PIL import Image
from sentence_transformers import SentenceTransformer
from django.core.files.storage import default_storage
from django.utils import timezone
import numpy as np

# Set cache directory to pre-downloaded model location
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "/app/models"

logger = logging.getLogger(__name__)


class ImageEmbeddingService:
    """Service for generating and managing image embeddings using CLIP."""

    def __init__(self, model_name: str = "sentence-transformers/clip-ViT-B-32"):
        """
        Initialize the embedding service with a specific CLIP model.

        Args:
            model_name: Name of the sentence-transformers CLIP model to use
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy loading of the model to avoid loading it on import."""
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {str(e)}")
                logger.error(
                    "💡 Run 'python manage.py download_model' to pre-download the model"
                )
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
                raise
        return self._model

    def generate_embedding(self, image_path: str) -> Optional[List[float]]:
        """
        Generate an embedding for an image.

        Args:
            image_path: Path to the image file (can be local or S3)

        Returns:
            List of floats representing the embedding, or None if error
        """
        try:
            # Open image using Django's storage backend (works with S3 or local)
            with default_storage.open(image_path, "rb") as image_file:
                image = Image.open(image_file)

                # Convert to RGB if needed (CLIP expects RGB)
                if image.mode != "RGB":
                    image = image.convert("RGB")

                # Generate real CLIP embedding
                embedding = self.model.encode([image])[0]

                # Convert numpy array to list for JSON serialization
                return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating embedding for {image_path}: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using CLIP text encoder.
        The sentence-transformers CLIP model can encode both images and text
        into the same semantic space.

        Args:
            text: Text string to encode

        Returns:
            List of floats representing the embedding, or None if error
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding generation")
                return None

            # Generate CLIP text embedding
            embedding = self.model.encode([text])[0]

            # Convert numpy array to list for JSON serialization
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating text embedding: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def combine_embeddings(
        self,
        image_embeddings: List[List[float]],
        text_embedding: List[float],
        image_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> Optional[List[float]]:
        """
        Combine multiple image embeddings with text embedding using weighted average.

        Args:
            image_embeddings: List of image embedding vectors
            text_embedding: Text embedding vector
            image_weight: Weight for image embeddings (default 0.7)
            text_weight: Weight for text embedding (default 0.3)

        Returns:
            Combined and normalized embedding, or None if error

        Steps:
        1. Average all image embeddings
        2. Weighted combination with text embedding
        3. Normalize the result (L2 normalization for cosine similarity)
        """
        try:
            if not image_embeddings:
                logger.error("No image embeddings provided for combination")
                return None

            if not text_embedding:
                logger.warning("No text embedding provided, using only image embeddings")
                # Use only image embeddings
                avg_image_emb = np.mean(image_embeddings, axis=0)
                # Normalize
                combined = avg_image_emb / np.linalg.norm(avg_image_emb)
                return combined.tolist()

            # Convert to numpy arrays
            image_embs_array = np.array(image_embeddings)
            text_emb_array = np.array(text_embedding)

            # Average all image embeddings
            avg_image_emb = np.mean(image_embs_array, axis=0)

            # Weighted combination (default: 70% images, 30% text)
            combined = image_weight * avg_image_emb + text_weight * text_emb_array

            # L2 normalize for cosine similarity
            norm = np.linalg.norm(combined)
            if norm == 0:
                logger.error("Combined embedding has zero norm")
                return None

            combined = combined / norm

            # Convert to list for JSON serialization
            return combined.tolist()

        except Exception as e:
            logger.error(f"Error combining embeddings: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def generate_embedding_for_post_image(self, post_image) -> bool:
        """
        Generate and save embedding for a PostImage instance.

        Args:
            post_image: PostImage instance

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(post_image.image.name)

            if embedding is None:
                return False

            # Update the PostImage instance
            post_image.embedding = embedding
            post_image.embedding_model = self.model_name
            post_image.embedding_generated_at = timezone.now()
            post_image.save(
                update_fields=["embedding", "embedding_model", "embedding_generated_at"]
            )

            return True

        except Exception as e:
            logger.error(
                f"Error generating embedding for PostImage {post_image.id}: {str(e)}"
            )
            return False

    def generate_combined_embedding_for_post(self, post) -> bool:
        """
        Generate and save combined embedding for a Post instance.

        Args:
            post: Post instance with related images

        Returns:
            True if successful, False otherwise

        Steps:
        1. Get all PostImage instances for this post
        2. Verify all have embeddings
        3. Generate text embedding for caption
        4. Combine embeddings
        5. Save to post.combined_embedding
        """
        try:
            # Get all PostImage instances for this post
            post_images = post.images.all()

            if not post_images.exists():
                logger.error(f"Post {post.id} has no images")
                return False

            # Collect image embeddings
            image_embeddings = []
            for img in post_images:
                if img.embedding is None or (
                    hasattr(img.embedding, "__len__") and len(img.embedding) == 0
                ):
                    logger.warning(
                        f"PostImage {img.id} for Post {post.id} has no embedding"
                    )
                    return False
                image_embeddings.append(img.embedding)

            logger.info(
                f"Collected {len(image_embeddings)} image embeddings for Post {post.id}"
            )

            # Generate text embedding for caption
            text_embedding = None
            if post.caption and post.caption.strip():
                text_embedding = self.generate_text_embedding(post.caption)
                if text_embedding is None:
                    logger.warning(
                        f"Failed to generate text embedding for Post {post.id}, "
                        "will use only image embeddings"
                    )

            # Combine embeddings
            combined_embedding = self.combine_embeddings(
                image_embeddings, text_embedding
            )

            if combined_embedding is None:
                logger.error(f"Failed to combine embeddings for Post {post.id}")
                return False

            # Update the Post instance
            post.combined_embedding = combined_embedding
            post.combined_embedding_model = self.model_name
            post.combined_embedding_generated_at = timezone.now()
            post.save(
                update_fields=[
                    "combined_embedding",
                    "combined_embedding_model",
                    "combined_embedding_generated_at",
                ]
            )

            logger.info(
                f"Successfully generated combined embedding for Post {post.id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error generating combined embedding for Post {post.id}: {str(e)}"
            )
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score between -1 and 1 (higher is more similar)
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            magnitude1 = np.linalg.norm(vec1)
            magnitude2 = np.linalg.norm(vec2)

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            similarity = dot_product / (magnitude1 * magnitude2)
            return float(similarity)

        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0


# Global instance for reuse
_embedding_service = None


def get_embedding_service() -> ImageEmbeddingService:
    """Get a singleton instance of the embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = ImageEmbeddingService()
    return _embedding_service

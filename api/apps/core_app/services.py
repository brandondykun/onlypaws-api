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

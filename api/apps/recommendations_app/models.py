"""
Recommendations app models.
"""

from django.db import models
from pgvector.django import VectorField


class ProfilePreferenceEmbedding(models.Model):
    """
    Long-term taste embedding for a Profile, derived from PostInteraction history.

    Stored in the same 512-dim CLIP-ViT-B-32 space as Post.combined_embedding so it
    can be used directly as a query vector against the post HNSW index.
    """

    profile = models.OneToOneField(
        "profile_app.Profile",
        on_delete=models.CASCADE,
        related_name="preference_embedding",
    )
    embedding = VectorField(
        dimensions=512,
        null=True,
        blank=True,
        help_text="Weighted-average embedding of the profile's recent post interactions.",
    )
    last_computed_at = models.DateTimeField(null=True, blank=True)
    # Audit field — snapshot of the profile's interaction count when this
    # embedding was last persisted. Not used at request time; α blending
    # reads a live cached count via services._recent_interaction_count.
    interaction_count_at_last_compute = models.PositiveIntegerField(default=0)
    embedding_model = models.CharField(
        max_length=100,
        default="sentence-transformers/clip-ViT-B-32",
    )

    class Meta:
        indexes = [
            models.Index(fields=["last_computed_at"]),
        ]

    def __str__(self):
        return f"PreferenceEmbedding for profile {self.profile_id}"

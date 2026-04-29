"""
Admin configuration for recommendations app.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ProfilePreferenceEmbedding


@admin.register(ProfilePreferenceEmbedding)
class ProfilePreferenceEmbeddingAdmin(ModelAdmin):
    list_display = [
        "profile",
        "last_computed_at",
        "interaction_count_at_last_compute",
        "embedding_model",
        "has_embedding",
    ]
    list_filter = ["embedding_model", "last_computed_at"]
    search_fields = ["profile__username"]
    readonly_fields = [
        "profile",
        "last_computed_at",
        "interaction_count_at_last_compute",
        "embedding_model",
        "has_embedding",
    ]
    exclude = ["embedding"]

    def has_embedding(self, obj):
        return obj.embedding is not None

    has_embedding.boolean = True
    has_embedding.short_description = "Has embedding"

    def has_add_permission(self, request):
        return False

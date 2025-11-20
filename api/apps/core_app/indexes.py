"""
Database Indexes.
"""


# your_app/indexes.py
from django.contrib.postgres.indexes import PostgresIndex
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.models import Model
from django.db.models.indexes import Index


class HnswIndex(PostgresIndex):
    """
    HNSW index for pgvector fields using cosine distance.
    Usage:
        indexes = [
            HnswIndex(
                fields=["combined_embedding"],
                name="post_embedding_hnsw_idx",
                opclasses=["vector_cosine_ops"],
                # Optional HNSW parameters
                m=16,
                ef_construction=64,
            )
        ]
    """
    
    suffix = "hnsw"

    def __init__(self, *, m: int = 16, ef_construction: int = 64, **kwargs):
        self.m = m
        self.ef_construction = ef_construction
        super().__init__(**kwargs)

    def create_sql(self, model, schema_editor, **kwargs):
        # Start with the base SQL from Django
        statement = super().create_sql(model, schema_editor, **kwargs)

        # Set the index type to hnsw
        statement.parts["index_type"] = "hnsw"

        # Add HNSW parameters
        hnsw_params = f"m = {self.m}, ef_construction = {self.ef_construction}"
        if statement.parts.get("extra"):
            statement.parts["extra"] += f" WITH ({hnsw_params})"
        else:
            statement.parts["extra"] = f"WITH ({hnsw_params})"

        return statement

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        # Preserve our custom parameters
        if self.m != 16:
            kwargs["m"] = self.m
        if self.ef_construction != 64:
            kwargs["ef_construction"] = self.ef_construction
        return path, args, kwargs
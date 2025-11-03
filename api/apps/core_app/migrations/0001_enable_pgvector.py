"""
Migration to enable pgvector extension.
This must run before any migrations that use vector fields.
"""
from django.db import migrations


class Migration(migrations.Migration):
    """
    Enable pgvector extension in PostgreSQL database.
    This is required for vector field support in PostImage model.
    """

    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
    ]


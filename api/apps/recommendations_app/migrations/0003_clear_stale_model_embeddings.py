"""
Clear preference embeddings stamped with the old model name.

Migration 0001 set the embedding_model default to "clip-vit-base-patch32";
0002 changed it to "sentence-transformers/clip-ViT-B-32". Any rows created
between those migrations carry the old name, and services._load_long_term
silently skips them as "model mismatch" — those users are stuck on
short-term-only recs until the next compute lands.

Wipe the stale embedding/timestamp pair so the existing nightly + 6-hourly
sweeps treat them as missing and recompute on the next run.
"""

from django.db import migrations


CURRENT_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"


def clear_stale_embeddings(apps, schema_editor):
    ProfilePreferenceEmbedding = apps.get_model(
        "recommendations_app", "ProfilePreferenceEmbedding"
    )
    ProfilePreferenceEmbedding.objects.exclude(
        embedding_model=CURRENT_MODEL_NAME
    ).update(
        embedding=None,
        last_computed_at=None,
        embedding_model=CURRENT_MODEL_NAME,
    )


def noop_reverse(apps, schema_editor):
    # The pre-clear state can't be reconstructed: we don't store the original
    # vectors anywhere else. Leaving this as a no-op is the only safe reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("recommendations_app", "0002_alter_profilepreferenceembedding_embedding_model"),
    ]

    operations = [
        migrations.RunPython(clear_stale_embeddings, noop_reverse),
    ]

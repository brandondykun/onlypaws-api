# Backfill public_id for all existing rows in posts_app

import ulid
from django.db import migrations


def backfill_public_id(apps, schema_editor):
    Post = apps.get_model('posts_app', 'Post')
    PostImage = apps.get_model('posts_app', 'PostImage')
    SavedPost = apps.get_model('posts_app', 'SavedPost')
    PostImageTag = apps.get_model('posts_app', 'PostImageTag')
    PostImageScaled = apps.get_model('posts_app', 'PostImageScaled')

    for model in (Post, PostImage, SavedPost, PostImageTag, PostImageScaled):
        for obj in model.objects.filter(public_id__isnull=True):
            obj.public_id = ulid.new()
            obj.save(update_fields=['public_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0008_add_public_id'),
    ]

    operations = [
        migrations.RunPython(backfill_public_id, noop),
    ]

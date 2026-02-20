# Generated manually for public_id (ULID) on all posts_app models

from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0007_add_post_status_and_postimage_scaled'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='postimage',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='savedpost',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='postimagetag',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='postimagescaled',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
    ]

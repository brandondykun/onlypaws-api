# Set public_id to non-null after backfill

from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0009_backfill_public_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimage',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='savedpost',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimagetag',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimagescaled',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
    ]

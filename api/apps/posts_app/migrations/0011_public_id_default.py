# Add default=ulid.new to public_id so new instances get a ULID automatically

import ulid
from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0010_public_id_not_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimage',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='savedpost',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimagetag',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='postimagescaled',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
    ]

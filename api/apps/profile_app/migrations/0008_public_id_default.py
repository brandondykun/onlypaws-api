# Add default=ulid.new to public_id so new instances get a ULID automatically

import ulid
from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('profile_app', '0007_public_id_not_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pettype',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profileimage',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profileimagescaled',
            name='public_id',
            field=ULIDField(default=ulid.new, editable=False, unique=True),
        ),
    ]

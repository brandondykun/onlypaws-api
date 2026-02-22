# Set public_id to non-null after backfill

from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('profile_app', '0006_backfill_public_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pettype',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profileimage',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='profileimagescaled',
            name='public_id',
            field=ULIDField(editable=False, unique=True),
        ),
    ]

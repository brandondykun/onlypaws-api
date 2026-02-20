# Generated manually for public_id (ULID) on all profile_app models

from django.db import migrations
from django_ulid.models import ULIDField


class Migration(migrations.Migration):

    dependencies = [
        ('profile_app', '0004_profile_image_presigned_and_scaled'),
    ]

    operations = [
        migrations.AddField(
            model_name='pettype',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='address',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='profileimage',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='profileimagescaled',
            name='public_id',
            field=ULIDField(editable=False, null=True, unique=True),
        ),
    ]
